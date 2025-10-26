# Comp Implementation Tasks

**Chapter 01 Complete! We have a full parser for core Comp syntax.**

This is a plan to reach the midpoint of the Comp language. This is broken into
chapters split into a series of phases. Each phase will be represented by
a document in the project tasks/ directory.

This directory contains numbered phase files that track implementation milestones.


## 01. Basic Parsing

Focused just on parsing the main language features into ast trees

[X] Project setup - Create uv project, directory structure, starting point
[X] Number Literals - Implement lark parser, parse number literals
[X] String Literals - Parse string literals and identifiers
[X] References - Parse function, string, and shape references
[X] Structures - Parse structures with fields, nested structures
[X] Mathematical Operators - Parse arithmetic, comparison, logical operators, parentheses
[X] Advanced Operators - Parse assignment, structure, pipeline, block operators
[X] Scopes and Assignments - Parse scope operators and references ($ctx, $mod, $in, $out, ^, @)
[X] Pipeline Operations - Parse statements and pipelines (flat operation lists)
[X] Rework grammar, astnodes, and unit tests
[X] Tag Definitions - Module-level grammar, parse tag definitions (no values yet)
[X] Shapes - Parse shape definitions
[X] Function - Parse function definitions
[X] Tags Complete - Complete parsing of tags with values, extensions, and generation functions
[X] Multiline strings

**Chapter 01 Complete! We have a full parser for core Comp syntax.**

## 02. Values and Expressions

Initial runtime structures and data

[X] Runtime Values - Create value types (Number, String, Structure, etc.)
[X] Expression Evaluation - Evaluate arithmetic and logical expressions
[X] Identifier Resolution - Implement scope lookup (@, ^, $)
[X] Extended field name types, (numbers, tags)
[X] Core builtin tag types
[X] Core builtin shapes
[X] Structure Building - Create and manipulate structures
[X] Pipeline Execution - Execute pipeline operations with seed/ops
[X] Function Definitions
[X] Shape matching and morphing
[X] Blocks (definition and shaping and invoke)
[X] Initial minimal conditional and iteration
[X] Failure and fallbacks
[X] Builtin Functions - Minimal set of core functions
[X] Function dispatch
[X] Tag polymorphic dispatch

## CC. Library Incubation

Initial pass at some of core language libraries. 
These must be hardcoded into a global namespace until imports arrive

[ ] String and Number
[~] Conditionals and Loops
[ ] Tag management and introspection
[ ] Stubbed in IO (print, file-to-string)

## CC. Complete Parsing

Finish parsing all langauge features into ast nodes

[X] Docstrings
[ ] Detached Docstrings
[ ] Units
[ ] Imports
[X] Resources
[ ] Trails
[ ] Placeholder operator ???

## CC. Modules

Structure for code, no more "everything in one global"

[X] Single file module imports
[X] Main and entry entrypoints
[ ] Python module binding
[X] Standalone comp command line
[ ] Directory modules

## CC. Continued Core Language

[X] String templates
[ ] Pure functions
[X] Streams
[X] Private data
[ ] Lazy Evaluation (scope captures)
[ ] Resources and tracking
[ ] Describe
[ ] String Units
[ ] Number Units
[ ] Store

## CC. Future

Things that likely won't be addressed until much more ecosystem arrives

[ ] Filesystem 
[ ] Idiomatic comp bindings for std python libs
[ ] Transactions
[ ] Type constraints
