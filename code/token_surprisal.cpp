// Token-level causal surprisal using llama.cpp's C API.
//
// Usage: token_surprisal MODEL MANIFEST OUTPUT [N_CTX] [N_BATCH]
// MANIFEST is tab-separated: document_id<TAB>UTF-8-text-file.
// OUTPUT columns are document, token_index, byte_start, byte_end, nll_nats.

#include <llama.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static std::string read_file(const std::string & path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot read " + path);
    std::ostringstream buffer;
    buffer << in.rdbuf();
    return buffer.str();
}

static std::vector<llama_token> tokenize(
        const llama_vocab * vocab, const std::string & text) {
    int32_t required = llama_tokenize(
        vocab, text.data(), static_cast<int32_t>(text.size()), nullptr, 0,
        false, false);
    if (required >= 0) return {};
    std::vector<llama_token> tokens(static_cast<size_t>(-required));
    int32_t count = llama_tokenize(
        vocab, text.data(), static_cast<int32_t>(text.size()), tokens.data(),
        static_cast<int32_t>(tokens.size()), false, false);
    if (count < 0) throw std::runtime_error("tokenization failed");
    tokens.resize(static_cast<size_t>(count));
    return tokens;
}

static std::string token_piece(const llama_vocab * vocab, llama_token token) {
    std::vector<char> buffer(256);
    int32_t count = llama_token_to_piece(
        vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0,
        true);
    if (count < 0) {
        buffer.resize(static_cast<size_t>(-count));
        count = llama_token_to_piece(
            vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()),
            0, true);
    }
    if (count < 0) throw std::runtime_error("token rendering failed");
    return std::string(buffer.data(), static_cast<size_t>(count));
}

static double target_nll(
        const float * logits, int32_t vocab_size, llama_token target) {
    float maximum = -std::numeric_limits<float>::infinity();
    for (int32_t i = 0; i < vocab_size; ++i) maximum = std::max(maximum, logits[i]);
    double denominator = 0.0;
    for (int32_t i = 0; i < vocab_size; ++i) {
        denominator += std::exp(static_cast<double>(logits[i] - maximum));
    }
    return std::log(denominator) + maximum - logits[target];
}

int main(int argc, char ** argv) {
    if (argc < 4 || argc > 6) {
        std::cerr << "usage: token_surprisal MODEL MANIFEST OUTPUT [N_CTX] [N_BATCH]\n";
        return 2;
    }
    const uint32_t n_ctx = argc >= 5 ? static_cast<uint32_t>(std::stoul(argv[4])) : 8192;
    const uint32_t n_batch = argc >= 6 ? static_cast<uint32_t>(std::stoul(argv[5])) : 256;

    llama_backend_init();
    llama_model_params model_params = llama_model_default_params();
    model_params.n_gpu_layers = -1;
    llama_model * model = llama_model_load_from_file(argv[1], model_params);
    if (!model) throw std::runtime_error("model load failed");
    const llama_vocab * vocab = llama_model_get_vocab(model);
    const int32_t vocab_size = llama_vocab_n_tokens(vocab);

    llama_context_params context_params = llama_context_default_params();
    context_params.n_ctx = n_ctx;
    context_params.n_batch = n_batch;
    context_params.n_ubatch = n_batch;
    context_params.n_outputs_max = n_batch;
    context_params.n_threads = 10;
    context_params.n_threads_batch = 10;
    context_params.offload_kqv = true;
    llama_context * context = llama_init_from_model(model, context_params);
    if (!context) throw std::runtime_error("context creation failed");

    std::ifstream manifest(argv[2]);
    std::ofstream output(argv[3]);
    if (!manifest || !output) throw std::runtime_error("manifest/output open failed");
    output << "document\ttoken_index\tbyte_start\tbyte_end\tnll_nats\n";

    std::string line;
    size_t document_count = 0;
    while (std::getline(manifest, line)) {
        const size_t tab = line.find('\t');
        if (tab == std::string::npos) continue;
        const std::string document = line.substr(0, tab);
        const std::string path = line.substr(tab + 1);
        const std::string text = read_file(path);
        std::vector<llama_token> tokens = tokenize(vocab, text);
        if (tokens.size() < 2 || tokens.size() > n_ctx) {
            std::cerr << "skip " << document << " tokens=" << tokens.size() << "\n";
            continue;
        }

        std::vector<size_t> starts(tokens.size()), ends(tokens.size());
        size_t cursor = 0;
        for (size_t i = 0; i < tokens.size(); ++i) {
            starts[i] = cursor;
            cursor += token_piece(vocab, tokens[i]).size();
            ends[i] = cursor;
        }
        llama_memory_clear(llama_get_memory(context), true);
        for (size_t start = 0; start < tokens.size(); start += n_batch) {
            const int32_t count = static_cast<int32_t>(
                std::min(static_cast<size_t>(n_batch), tokens.size() - start));
            llama_batch batch = llama_batch_init(count, 0, 1);
            batch.n_tokens = count;
            for (int32_t k = 0; k < count; ++k) {
                batch.token[k] = tokens[start + static_cast<size_t>(k)];
                batch.pos[k] = static_cast<llama_pos>(start + static_cast<size_t>(k));
                batch.n_seq_id[k] = 1;
                batch.seq_id[k][0] = 0;
                batch.logits[k] = 1;
            }
            const int32_t status = llama_decode(context, batch);
            if (status != 0) throw std::runtime_error("decode failed for " + document);
            for (int32_t k = 0; k < count; ++k) {
                const size_t input_index = start + static_cast<size_t>(k);
                const size_t target_index = input_index + 1;
                if (target_index >= tokens.size()) break;
                const float * logits = llama_get_logits_ith(context, k);
                const double nll = target_nll(logits, vocab_size, tokens[target_index]);
                output << document << '\t' << target_index << '\t'
                       << starts[target_index] << '\t' << ends[target_index]
                       << '\t' << nll << '\n';
            }
            llama_batch_free(batch);
        }
        ++document_count;
        std::cerr << "scored " << document_count << " " << document
                  << " tokens=" << tokens.size() << "\n";
    }

    llama_free(context);
    llama_model_free(model);
    llama_backend_free();
    return 0;
}
