# Comp Implementation Tasks

**Chapter 01 Complete! We have a full parser for core Comp syntax.**

This is a plan to reach the midpoint of the Comp language. This is broken into
chapters split into a series of phases. Each phase will be represented by
a document in the project tasks/ directory.

This directory contains numbered phase files that track implementation milestones.


## 01. Basic Parsing

Focused just on parsing the main language features into ast trees

[X] 01-01. Project setup - Create uv project, directory structure, starting point
[X] 01-02. Number Literals - Implement lark parser, parse number literals
[X] 01-03. String Literals - Parse string literals and identifiers
[X] 01-04. References - Parse function, string, and shape references
[X] 01-05. Structures - Parse structures with fields, nested structures
[X] 01-06. Mathematical Operators - Parse arithmetic, comparison, logical operators, parentheses
[X] 01-07. Advanced Operators - Parse assignment, structure, pipeline, block operators
[X] 01-08. Scopes and Assignments - Parse scope operators and references ($ctx, $mod, $in, $out, ^, @)
[X] 01-09. Pipeline Operations - Parse statements and pipelines (flat operation lists)
[X] 01-10. Rework grammar, astnodes, and unit tests
[X] 01-11. Tag Definitions - Module-level grammar, parse tag definitions (no values yet)
[X] 01-12. Shapes - Parse shape definitions
[X] 01-13. Function - Parse function definitions
[X] 01-14. Tags Complete - Complete parsing of tags with values, extensions, and generation functions
[X] 01-15. Multiline strings

**Chapter 01 Complete! We have a full parser for core Comp syntax.**

## 02. Values and Expressions

Initial runtime structures and data

[X] 02-01. Runtime Values - Create value types (Number, String, Structure, etc.)
[X] 02-02. Expression Evaluation - Evaluate arithmetic and logical expressions
[X] 02-03. Identifier Resolution - Implement scope lookup (@, ^, $)
[X] 02-PP. Extended field name types, (numbers, tags)
[X] 02-PP. Core builtin tag types
[X] 02-PP. Core builtin shapes
[X] 02-PP. Structure Building - Create and manipulate structures
[X] 02-PP. Pipeline Execution - Execute pipeline operations with seed/ops
[X] 02-PP. Function Definitions
[X] 02-PP. Shape matching and morphing
[X] 02-PP. Blocks (definition and shaping and invoke)
[X] 02-PP. Initial minimal conditional and iteration
[X] 02-PP. Failure and fallbacks
[X] 02-PP. Builtin Functions - Minimal set of core functions
[X] CC-PP. Function dispatch
[X] CC-PP. Tag polymorphic dispatch

## CC. Library Incubation

Initial pass at some of core language libraries. 
These must be hardcoded into a global namespace until imports arrive

[ ] CC-PP. String and Number
[~] CC-PP. Conditionals and Loops
[ ] CC-PP. Tag management and introspection
[ ] CC-PP. Stubbed in IO (print, file-to-string)

## CC. Complete Parsing

Finish parsing all langauge features into ast nodes

[ ] CC-PP. Docstrings
[ ] CC-PP. Units
[ ] CC-PP. Imports
[ ] CC-PP. Resources
[ ] CC-PP. Trails
[ ] CC-PP. Placeholder operator ???

## CC. Modules

Structure for code, no more "everything in one global"

[ ] CC-PP. Single file module imports
[ ] CC-PP. Main and entry entrypoints
[ ] CC-PP. Python module binding
[ ] CC-PP. Standalone comp command line
[ ] CC-PP. Directory modules

## CC. Continued Core Language

[ ] 02-PP. String templates
[ ] 02-PP. Pure functions
[ ] 02-PP. Streams
[ ] CC-PP. Private data
[ ] CC-PP. Lazy Evaluation (scope captures)
[ ] CC-PP. Resources and tracking
[ ] CC-PP. Describe
[ ] CC-PP. String Units
[ ] CC-PP. Number Units
[ ] CC-PP. Store

## CC. Future

Things that likely won't be addressed until much more ecosystem arrives

[ ] CC-PP. Filesystem 
[ ] CC-PP. Idiomatic comp bindings for std python libs
[ ] CC-PP. Transactions
[ ] CC-PP. Type constraints