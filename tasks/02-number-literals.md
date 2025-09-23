# Phase 02: Number Literal Parsing

**Status**: ✅ COMPLETED  
**Started**: September 2025  
**Completed**: September 23, 2025

## Goals

Implement complete number literal parsing for the Comp language, supporting all number formats specified in the design documents.

## What We're Building

### Number Parsing Engine
- **Decimal numbers**: Leverage `decimal.Decimal` for precision and special values
- **Alternative bases**: Binary (`0b`), octal (`0o`), hexadecimal (`0x`) with underscore support
- **Scientific notation**: Full support via `decimal.Decimal`
- **Special values**: `inf`, `-inf`, `nan` as tagged values
- **Underscores**: Support for readability in all bases

### Parser Architecture
- **Tokenizer**: Recognize number patterns vs other tokens
- **Base detection**: Identify prefixes and route to appropriate parsers
- **AST nodes**: Create proper number literal nodes with type information
- **Error handling**: Clear messages for malformed numbers

## Success Criteria

- [x] Parse all `decimal.Decimal` supported formats
- [x] Parse binary literals: `0b1010_1010`
- [x] Parse octal literals: `0o755`
- [x] Parse hexadecimal literals: `0xFF_FF`
- [x] Support underscores in all number formats
- [x] Handle signed numbers: `+42`, `-0xFF`
- [x] Provide clear error messages for invalid number formats
- [x] All number tests in `test_number_literals.py` pass (12/12)
- [x] Precision preservation for large numbers and decimals
- [x] Bigint support for numbers larger than 64-bit

## ✅ Implementation Completed

### Core Architecture Delivered
- **Lark Grammar**: Streamlined `numbers.lark` with direct terminal matching
- **Parser Module**: `_numbers.py` leveraging Python stdlib (`ast.literal_eval`, `decimal.Decimal`)
- **AST Integration**: `NumberLiteral` nodes with `decimal.Decimal` values
- **Comprehensive Tests**: 12 tests covering all formats, precision, and edge cases

### Technical Highlights
- **Standard Library First**: Used `ast.literal_eval()` for integer parsing, `decimal.Decimal()` for precision
- **Grammar Streamlining**: Reduced from 30+ lines to 15 lines while maintaining full functionality  
- **Precision Preservation**: All numbers stored as `decimal.Decimal` to avoid float precision loss
- **Robust Detection**: Fixed scientific notation detection to avoid conflicts with hex digits
- **Modular Design**: Clean separation between grammar, parsing, and AST construction

### Key Files Created/Modified
- `src/comp/lark/numbers.lark` - Streamlined number grammar
- `src/comp/_numbers.py` - Number parsing implementation  
- `src/comp/_ast.py` - AST node definitions
- `src/comp/_parser.py` - Main parser interface
- `tests/test_number_literals.py` - Comprehensive test suite (12 tests)

## Implementation Strategy

### Phase 1: Basic Decimal Parsing
1. **Create AST node**: `NumberLiteral` class
2. **Basic tokenizer**: Identify number vs non-number tokens
3. **Decimal parser**: Use `decimal.Decimal` for all decimal formats
4. **Test foundation**: Get basic tests passing

### Phase 2: Alternative Bases
1. **Prefix detection**: Recognize `0b`, `0o`, `0x` prefixes
2. **Base conversion**: Convert to decimal, then to `Decimal`
3. **Underscore handling**: Strip underscores before parsing
4. **Validation**: Ensure digits are valid for their base

### Phase 3: Special Values and Edge Cases
1. **Tagged special values**: Map `inf`/`nan` to `#inf.num`/`#nan.num`
2. **Error handling**: Comprehensive error messages
3. **Edge case testing**: Boundary conditions and malformed input

## Files to Create

- `src/comp/ast_nodes.py` - AST node definitions
- `src/comp/tokenizer.py` - Basic tokenization  
- `src/comp/number_parser.py` - Number-specific parsing logic
- `src/comp/parser.py` - Main parser interface
- Update existing test files as needed

## Number Format Reference

Based on `design/type.md` and `decimal.Decimal` testing:

### Decimal Formats (via decimal.Decimal)
```
42              # Basic integer
-17.5           # Negative decimal  
1_000_000       # Underscores for readability
3.14159         # Precision decimals
1e3             # Scientific notation
1.23e-4         # Scientific with decimal
.5              # Leading decimal point
5.              # Trailing decimal point
inf, -inf, nan  # Special values
```

### Alternative Bases (custom parsing)
```
0b1010_1010     # Binary with underscores
0o755           # Octal
0xFF_FF         # Hexadecimal (mixed case OK)
```

## What We're NOT Building (Yet)

- String literal parsing → **Next: Phase 03**
- Tag parsing (beyond number literals)
- Complex expressions or operators
- Structure literals
- Any other language constructs

## 🎯 Ready for Phase 03: Tag and String Literals

Phase 02 established the foundational parser architecture and iterative refinement process. The streamlined approach of "grammar serves code, not vice versa" is ready to apply to the next literal types.

## Notes

- Leverage `decimal.Decimal` heavily to avoid reimplementing number parsing
- Focus on clear error messages - parsing failures should be informative
- Keep the architecture extensible for adding other literal types later
- All parsing should be deterministic and well-tested