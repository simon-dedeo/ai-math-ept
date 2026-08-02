/-
Return construction and lexical-scope ranges of tactic-style `have` declarations.

The program reads NUL-separated Lean terms from stdin and writes one line per
term.  Each successful line is a comma-separated list of
`start:constructionEnd:scopeEnd` byte ranges; `ERROR` records a parser failure.
The scope endpoint is the tail of the nearest enclosing tactic sequence.
Parsing, rather than elaboration, is intentional: ranges remain available even
when a proof depends on a historical Mathlib environment.
-/
import Mathlib

open Lean

structure HaveRange where
  start : String
  constructionEnd : String
  scopeEnd : String

partial def haveRanges (stx : Syntax) (scopeEnd : Option String := none) : Array HaveRange := Id.run do
  let mut ranges := #[]
  let scopeEnd :=
    if stx.getKind == ``Lean.Parser.Tactic.tacticSeq then
      stx.getTailPos?.map (fun position => toString position.byteIdx)
    else
      scopeEnd
  if stx.getKind == ``Lean.Parser.Tactic.tacticHave__ then
    if let (some start, some tail, some scopeTail) :=
        (stx.getPos?, stx.getTailPos?, scopeEnd) then
      ranges := ranges.push {
        start := toString start.byteIdx
        constructionEnd := toString tail.byteIdx
        scopeEnd := scopeTail
      }
  for arg in stx.getArgs do
    ranges := ranges ++ haveRanges arg scopeEnd
  return ranges

def renderRanges (ranges : Array HaveRange) : String :=
  String.intercalate "," <| ranges.toList.map fun range =>
    s!"{range.start}:{range.constructionEnd}:{range.scopeEnd}"

unsafe def main (_args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let env ← importModules #[{module := `Mathlib}] {} (loadExts := true)
  let stdin ← IO.getStdin
  let input ← stdin.readToEnd
  for source in input.splitOn "\u0000" do
    match Parser.runParserCategory env `term source with
    | .error _ => IO.println "ERROR"
    | .ok stx => IO.println (renderRanges (haveRanges stx))
  return 0
