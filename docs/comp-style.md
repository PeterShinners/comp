# Comp Language Style Guide

This guide summarizes the core idioms and conventions for writing clear,
maintainable Comp code. It is intended for both human authors and code-
generating agents.

## Module Layout

- **Includes** Start the file with the includes. These can go anywhere in the
  file, but grouped at the start of the file is good context. Imports play such
  an important role in the namespace and feel of a module. Their early
  declaration helps readers understand the context of the code in this module.
- **General First** The file should start with the highest level and general
  public definitions. The private and internal details should be ordered at the
  bottom of the file.
- **Grouped Overloads** Functions with multiple definitions should generally be
  grouped together. Each overload must have a unique fully qualified name, even
  if they share the same final leaf portion of their name. Group into sections
  of related functionality, but should avoid separators more than block comments
  with information and examples.
- **Avoid Separators** Avoid ASCII banners and decorative separators. Group
  related functionality using block comments with information and examples, but
  do not use decorative lines or banners.

## General Principles

- **Helper Functions** Comp reads best when branching and repetitive code is
  moved into composable functions. Place a section of simple helper functions at
  the bottom. Use these to help functionality form a readable flow of pipelined
  operations.
- **Pure functions** Prefer pure functions in any situation that does not need
  handles or rely on other impure functions. A large function may be better to
  split into two parts to separate its pure and impure sections, assuming the
  pure portions are generally reusable.
- **Specific shape inputs** Prefer to use specific input shape definitions.
  Don't rely on ~any except for situations that really work with any type of
  input.
- **Parameters are for configuration** Parameters are intended to be ways to
  configure a tool, like flags for a command line tool. There isn't always a
  clear separation between "configuration" and "data to be worked on" but when
  it makes sense, use parameters properly.
- **Tag Hierarchies** Even simple or singular tags are useful to be placed in a
  small hierarchy. Avoid top level single tags for general use cases.
- **Private Definitions** Use Comp's private definition syntax (a trailing `&`
  on the definition). Do not use underscored names. Privates are also generally
  best at the bottom of a file.
- **Selective Imports** Your module's imports can significantly change the
  behavior of code in the module. Manage your imports selectively and
  intentionally. The narrower the scope of imports, the easier it is to
  understand the code's behavior. Note that import changes may cause problems at
  build time, so check callouts and validation on your module after changing
  imports.
- **Overloads** Rely on function overloads instead of functions with top level
  "if" and "else" blocks that span most of the function body.

## Whitespace

- **Single line** Prefer single lines for shorter pipelines and statements that
  fit on a single line.
- **Multiple lines** Longer statements should be split on lines. Each line
  should generally start with an operator, like `|`, to chain it to the previous
  line.
- **Indentation** Multi line statements should be indented inside of braces and
  parenthesis. Top level pipelines in a function are usually cleanest
  unindented. The conditional branches of an `!on` statement are generally on
  separate lines and not indented.
- **Brackets** There are situations where shallow indented statements can
  represent multiple levels of indentation. Feel free to put all closing
  brackets onto a single line.
- **Operator spaces** When multiple statements fit on a single line, the spacing
  should primarily be around the statements. When statements have their own
  line, prefer to use space separators around the operators.
- **Empty lines** Module statement operators should generally have at least one
  line of whitespace in between. Groups of related statements (like imports or
  tag definitions) can often be packed tighter to improve readability.

## Style

- **Flat** Prefer flatter code over nested code.
- **Fallbacks** Rely on simpler code that attempts fallible operations and
  provides a fallback, instead of trying to check and validate the operation
  ahead of time.
- **Bracket choice** Use `()` for computation and pipelines. Use `{}` for
  building data. When swapping between them while iterating on code, remember:
  `()` is "I'm computing a thing" and `{}` is "I'm constructing data." Let the
  intent guide the choice.

## Development

- **Run the `comp` CLI tool with the `--callouts` argument** to get additional
  warnings and validations about the code. Callout errors will prevent the
  module from building.