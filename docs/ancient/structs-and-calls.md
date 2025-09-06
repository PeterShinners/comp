# structs and calls

Want to return to a function defines and returns its structure. Remember that a struct with one item is the same as a struct. So its ez to define a rich struct as a separate function then return a single value of that type in multiple functions.

maybe we use `let` and `var` type keywords in the block to define which variables are exported as the struct and which are just temporary values?

```python
define User p {
	let name String {length=1..} = p.name|0
	let age Number {>0} = p.age|1
	let active Boolean = True
}

def CurrentUser {} {
  let {"Peter Shinners", 50} User
}
```

Need to review CUE syntax for defining types and constraints

`struct.name|index` allows defining fallbacks. this means “use name” if it is defined, otherwise iterate first index value. Could also be `struct.a|b` to use one name or the other.

Was also thinking a ternary syntax could be something like `default ? expression` . If any lookup in the expression is undefined then fallback on default. `1 ? object.pivot.x` 

One odd trick is that if `obj.0` indexes the first item, what if it is a scalar item wrapped in another, like the `CurrentUser` call above. Want to treat it as [`user.name`](http://user.name) , not `user.0.name` . or `{15}` to be worked with as `val`, not `val.0` .

This seems like an impassable design. WHATDO?

Feels like a function either needs to define a struct members itself or return a single struct

Maybe that means there are two types of definitions. A struct and a func. both have mostly the same syntax but the function can only have one return object (possibly named?)

Maybe this means a function is an ‘iterator’ or stream that returns any number (or a single) object of a type. This means caller needs to be aware if they are defining a struct or calling a function/iterator.

CurrentUser wants a way to define a function that takes no argument. Perhaps that means there is no “arg name” before block. How do callers call that function? Is there a special “None” object this method is attached to?

Something like `->` gets a value from a call and `=>` gets an iterator of values from an item. Single arrow called on a struct just iterates a random/first value. 

`->`  on struct = the struct

`->` on stream = first iterated value from struct

`=>` on struct = first value from stream

`=>` on stream gives the stream

```python
define User p {
	name: String & #1..
	age: Number & >=0
	active: bool & false
```