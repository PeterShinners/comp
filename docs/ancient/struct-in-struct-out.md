# Struct in Struct out

Every function takes a struct in instead of arguments (immutable too?)

I like this because it moves all the type annotations, docs, decorations, defaults into a separate thing, which can afford to be a little heavier than a list of parameters. sugar for when function name is the same as the struct name?

The return “struct out” doesn’t need to define anything, because the block of code that is the function is the struct definition… hmm…

```python
struct write {
	file= Io.file
	data= buffer
}

write.function send w {
	let size= Libc.write(w.file, w.data)
	size= size
}
```

Sort stdin lines

```python
Env.main {
	let lines = Env.stdin lines
	let sorted {lines key= str.function l {l length} sort
	sorted foreach l {
		{Env.stdout l} writeline
}

# or as a single liner

Env.main.func args {
	{Env.stdin lines, key= str.func l {l length}} sort foreach l {{Env.stdout l} writeline}
}

# Since statements are auto determined on assignments, this 'one liner' can be 
# line split without needing intermediates

Env.main.func args {
	{Env.stdin lines 
    key= str.func l {l length}
	} sort 
		foreach l {{Env.stdout l} writeline}
}
```

aesthetically seems workable, BUT

would like to see the “sort” before the messing with “key” . maybe not needed but it helps set up what this structure being built is used for.

Is the double {{ starting the for loop an precursor to lisp-like nested blocks for idiomatic code? If so do not want. 

Need some way to define what `type.func arg block`  all means. What is keen is that this also works for for loops.

Also thinking some ‘walrus operator’ to store locals ends up nicer than `let` statements, since it can be inline

But how to reference this function/struct and perhaps define methods on top of it? Remember I want to define shape of struct separate from the call?

```python
Point.construct None o {x=0 y=0} 
Point.construct Object o {x?=o.x y?=o.y ..!}
Point.construct Number i {x=i y=i}

Line.construct object a {Point, Point}
Line.define distance l {(l.0.x-l.1.x)**2 + (l.0.y-l.1.y)**2}
Line.define midpoint l {{l.1.x/2+0.x l.1.y/2+l.0.2} Point}

let lin= {0, {x=2,y=3}}
let dist= lin distance
let m= lin.midpoint
```

Multiple constructors feels messy. Also, must hard error if shape for any constructor is invalid, perhaps there is a default and all others must refer to the main.  So to create a default point requires `{} Point` ? Perhaps empty/None can be omitted

So calling a constructor on a type that does not exist is ok? Or should the struct be defined ahead of time? 

This is where “the function being the struct definition” gets a little tricky when combined with “wanting type conversions or constructors”. But want any type that returns a point to be a valid Point struct.

But since we want all the awesome type annotation, default, and shape to be defined also, adding that to each function is dumb. So if structs must be predeclared this is easier?

```python
type Point {
	x= Number  # DOC
	y= Number
}
type Line {
	a= Point  
	b= Point
}

Point.new None a {x=0 y=0}  # Also not needed as empty value uses number default?
Point.new Number n {x=n y=n}
# unneeded construct Point Type t {..t} 
# unneeded construct Line Type t {..t}

Line lin= {1, {2,3}} 

Line.func length Number l {(l.0.x-l.1.x)**2 + (l.0.y-l.1.y)**2}
Line.func midpoint Point l {{l.1.x/2+0.x l.1.y/2+l.0.2}}
```

Default constructor to just copy defined fields could be omitted. Instead of `let` use the type name to define a variable. Can Function be a type and we simply assign a variable? Remember we want anon functions (like when passing a key arg. Seems like that func needs a signature (which is another type))

```python
Func length= Line Number line {..}
Func midpoint= Line Point line {..}

midpoint = {Line Point} func line {..}  # func is passed two types

type SortArgs {iter= Object, key= {Object Comparable} Func}
sort= SortArgs Func s {..}
```

Trying to define classes as operations on a base type. Function definitions are from that type also

```python
Type.new Point {x=Number y=Number}
Type.new Line {Point Point}

Line.func length Number arg {..}
Line.func mid Point arg {..}
```

Seems less clean than using keywords. But if these are just language constructs that can be extended then that is amazing! Are these just functions? They could be.

These could be called “operators” that take a struct for metadata and a block. Does this mean things like “for” and “if” are also operators? That would be ideal. “if” metadata definition may need to be super fancy for else blocks?

Methods defined for a type should not modify the type itself. They should only be available in a namespace which searches all available namespaces for defined methods it can use. Different modules can import different namespaces.

```python
value.if {{Ctx.stdout "it happened"} writeline}
1..5.foreach v {{Ctx.stdout "counter {i}" writeline}
```

Remember, looking up attributes is dot operator. But can be any object. If not a literal but a value enclose in curlies. `obj.{key}` or `obj.{1.23}` . But 90% of the time it is just a literal value, so `obj.field` .

Perhaps there is a “default operator”, so `Type` and `Func` don’t need the dotting. No, default operator too strange.

```python
Type.add Point {x=Number y=Number}
Type.add Line {Point Point}
Line.func length Number arg {}
Line.func midpoint Point arg {}

key= Comparable.anonFunc Type arg {}
# or a predefined operator for defining funcs
key = SortKey arg {}
# cool but want to put this under a namespace, where does that go?
key = stdlib.SortKey arg {}
key = Iterable.sort.Key arg {}
```

These operators sort of invert the logic of left to right. Could they be rewritten as regular struct methods?

```python
{Point {x=Num y=Num}} type
{Line {Point Point}} type

{length Line Number arg {..}} function
{midpoint Line Point arg {..}} function
```

Not liking this. Perhaps there is syntax sugar for putting the method/op before the value. 

```python
type -> Point {x=Num y=Num}
type -> Line {Point Point}
func -> Line length Number arg {..}
func -> Line midpoint Point arg {..}
```

Functions need some way to define they take a literal. This could be equivalent of the above. It also assumes all following data defines a block, to avoid nesting one level of block? That does limit how and where it could be used, but perhaps clean for a most common case?

Or keywords (perhaps still defined as operators?) Need to statically analyze a file to know what ops/keywords are defined. Maybe a macro like rust, `type! Point {}` . Not immediately a fan…

So keywords are code defined operators. Although they need to be namespaced off some object. then all this becomes

```python
Type.new Point {x=Num y=Num}
Type.new Line {Point Point}
Func.new Line length Number arg {..}
Func.new Line midpoint Point arg {..}
```

Any function can also be used to access the type it returns. So something like `key= Object.sort.key val {val Number abs}`  . But remember these keyword/ops eat all remaining tokens and treat it as a struct, the curly brackets could be used explicitly. And also, they can be called like a regular method

```python
# all equivalent sugar?
Type.new Point {x=Num y=Num}
Type.new {Point {x=num y=Num}}
{Point {x=Num y=Num}} Type.new
```

Maybe the final is the preferred form anyways. Note, the struct that defines [Type.new](http://Type.new) needs a way to say it takes a “type” or “name” arg, which is a literal like we are seeing for `Point` ?

Or maybe all this to just get back to saying keywords are best? For type definitions this seems fine since we want those to be statements. But function definitions are different and we want to create them on the fly…

Maybe a separate to invoke methods, then it means curly braces aren’t needed around must structs?

```python
Point {x=Num y=Num} -> Type.new
```

This seems keen. Still feels like [`Type.new`](http://Type.new) could be a keyword since it is introducing a grammar to the namespace? Soemthing like a `define`?