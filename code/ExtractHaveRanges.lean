/-
Return the exact parser ranges of tactic-style `have` declarations.

The program reads NUL-separated Lean terms from stdin and writes one line per
term.  Each successful line is a comma-separated list of `start:end` byte
ranges; `ERROR` records a parser failure.  Parsing, rather than elaboration, is
intentional: ranges remain available even when a proof depends on a historical
Mathlib environment.
-/
import Mathlib

open Lean

partial def haveRanges (stx : Syntax) : Array (String × String) := Id.run do
  let mut ranges := #[]
  if stx.getKind == ``Lean.Parser.Tactic.tacticHave__ then
    if let (some start, some tail) := (stx.getPos?, stx.getTailPos?) then
      ranges := ranges.push (toString start.byteIdx, toString tail.byteIdx)
  for arg in stx.getArgs do
    ranges := ranges ++ haveRanges arg
  return ranges

def renderRanges (ranges : Array (String × String)) : String :=
  String.intercalate "," <| ranges.toList.map fun (start, tail) => s!"{start}:{tail}"

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
