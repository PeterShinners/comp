# Comp
Compositional computation language

**Shape-based data flow through chained pipelines**

Comp is a programming language designed around immutable data transformation through left-to-right pipelines. All data is treated as structures that flow through transformation functions, creating elegant and readable code for data processing, tool building, and computational workflows.

## Core Philosophy

Everything in Comp is data transformation. Instead of imperative commands that modify state, you express programs as pipelines where immutable structures flow through transformation functions. The language automatically handles type compatibility based on data shape rather than rigid type hierarchies.

```comp
# Read CSV, filter rows, transform data, write output
"/data/sales.csv" 
-> csv.read 
-> {row -> row.amount > 1000} 
-> {row -> {customer=row.name total=row.amount*1.1}} 
-> csv.write("/output/processed.csv")
```

## Key Features

- **Immutable data flow**: All structures are immutable; transformations create new data
- **Shape-based compatibility**: Functions work with any data that has the required structure
- **Pipeline syntax**: Left-to-right `->` operators for readable data transformations
- **Automatic type promotion**: Scalars automatically become structures when needed
- **Universal data model**: SQL results, JSON, function returns all handled identically

## Design Status

Comp is currently in **early design phase**. The language specification, syntax, and core concepts are being actively developed. This repository contains design documents, syntax explorations, and implementation planning.

## Early Design Documents

The `/docs/early-design/` directory contains the foundational design work:

- **[Design Decisions](docs/early-design/design-decisions.md)** - Key architectural choices and their rationale
- **[Syntax Comparison](docs/early-design/syntax-comparison.md)** - How Comp syntax compares to existing languages
- **[Language Specification](docs/early-design/language-spec.md)** - Detailed technical specification

## Contributing

Comp is in active design phase. Comments on language concepts, syntax, and use cases would be benefitial.

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

*Comp is designed for developers who work with data transformation, tool building, and computational workflows. The language emphasizes readability, immutability, and the natural flow of data through processing pipelines.*