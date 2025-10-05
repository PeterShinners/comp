#!/usr/bin/env python3
"""Debug Value equality and hashing."""

from src.comp.run import _value

# Test numeric values
v1 = _value.Value(8)
v2 = _value.Value(8)

print(f"v1 = {v1}")
print(f"v2 = {v2}")
print(f"v1 == v2: {v1 == v2}")
print(f"hash(v1): {hash(v1)}")
print(f"hash(v2): {hash(v2)}")
print(f"id(v1): {id(v1)}")
print(f"id(v2): {id(v2)}")

# Test dict lookup
d = {}
d[v1] = "first"
print(f"\nDict with v1 as key: {d}")
print(f"v1 in d: {v1 in d}")
print(f"v2 in d: {v2 in d}")
print(f"d[v2]: {d.get(v2, 'NOT FOUND')}")

# Test string values
s1 = _value.Value("computed")
s2 = _value.Value("computed")

print(f"\n\ns1 = {s1}")
print(f"s2 = {s2}")
print(f"s1 == s2: {s1 == s2}")
print(f"hash(s1): {hash(s1)}")
print(f"hash(s2): {hash(s2)}")

# Test dict lookup with strings
ds = {}
ds[s1] = "first"
print(f"\nDict with s1 as key: {ds}")
print(f"s1 in ds: {s1 in ds}")
print(f"s2 in ds: {s2 in ds}")
print(f"ds[s2]: {ds.get(s2, 'NOT FOUND')}")
