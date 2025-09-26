# Comp Implementation Tasks

See `AGENT.md` for complete development process and workflow details.

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
[ ] 01-07. Advanced Operators - Parse assignment, structure, pipeline, block, trail operators
[ ] 01-PP. Scopes and Assignments - Parse scope operators and references
[ ] 01-PP. Pipeline - Parse statements and pipelines
[ ] 01-PP. Tags Initial - Parse simple tag definitions (no values)
[ ] 01-PP. Shapes - Parse shape definitions
[ ] 01-PP. Function - Parse function definitions
[ ] 01-PP. Tags Complete - Complete parsing of tags with values
[ ] 01-PP. Non-definition Bang Operators - Parse !delete, !doc, etc.
[ ] 01-PP. Blocks and Args - Parsing of blocks and definition and passing function args

## CC. Values and Expressions

Initial runtime structures and data

[ ] CC-PP. Evaluate numerical expression operators
[ ] CC-PP. Implement scope referencing and overwriting
[ ] CC-PP. Structure creation
[ ] CC-PP. Structure operators
[ ] CC-PP. Core builtin tag types
[ ] CC-PP. Core builtin shapes
[ ] CC-PP. Handful of builtin example functions
[ ] CC-PP. Pipeline evaluation and failure propoagtion

## CC. Language Definitions

Allow creating the real object definitions for the language

[ ] CC-PP. Tag definitions
[ ] CC-PP. Shape Definitions and union shapes
[ ] CC-PP. Function Definitions
[ ] CC-PP. Placeholder operator ???
[ ] CC-PP. Blocks
[ ] CC-PP. Initial minimal conditional and iteration
[ ] CC-PP. Streams
[ ] CC-PP. Extended field name types, (numbers, tags)
[ ] CC-PP. Shape matching and morphing
[ ] CC-PP. String templates
[ ] CC-PP. Pure functions

## CC. Library Incubation

Initial pass at some of core language libraries. 
These must be hardcoded into a global namespace until imports arrive

[ ] CC-PP. String and Number
[ ] CC-PP. Conditionals and Loops
[ ] CC-PP. Tag management and introspection
[ ] CC-PP. Stubbed in IO (print, file-to-string)

## CC. Complete Parsing

Finish parsing all langauge features into ast nodes

[ ] CC-PP. Multiline strings
[ ] CC-PP. Docstrings
[ ] CC-PP. Units
[ ] CC-PP. Imports
[ ] CC-PP. Resources
[ ] CC-PP. Trails

## CC. Modules

Structure for code, no more "everything in one global"

[ ] CC-PP. Single file module imports
[ ] CC-PP. Main and entry entrypoints
[ ] CC-PP. Python module binding
[ ] CC-PP. Standalone comp command line
[ ] CC-PP. Directory modules

## CC. Continued Core Language

[ ] CC-PP. Private data
[ ] CC-PP. Function dispatch
[ ] CC-PP. Tag polymorphic dispatch
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