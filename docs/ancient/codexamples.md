# codexamples

python fibbonacci (strange because it prints intermediates)

```python
def fib(n):
   a,b = 0,1
   while a < n:
       print(a, end=' ')
       a, b = b, a+b
   print()
fib(1000)
```

my fib

```python
func fib {
  a = 0
  b = 1
	while n < arg {
	  << a
	  _next = a + b
	  a = b
	  b = _next
!fib(1000) .Io.stdout.log
```

fib seems sloppy

need operator to append item to iterator (and also iterator to iterator). an operator to get values from an iterator sort of replaces a for loop, and if condition. that takes a block argument. perhaps a ‘peek last value’ makes this entirely simpler

```jsx
func fib {Number} {
	<< 0
	<< num = 1
	while {.peeklast < arg} then {
		<< num = num + .peeklast
```

feels like heading to a large number of operators. for now, use literal method names to make things clearer?

need a way to separate local variables from outgoing data. perhaps now use an explicit namespace like local.var and export.var

these structures as iterators are treated as lazy structures, not like python iterators. they can be iterated multiple times.

```jsx
function fib {Number} {
	0, 1 .export.extend
	while {export.last < arg} {
		export.peek(-1) + export.peek(-2) .export.append
```

so are the iterated values from a structure a structure with a single value. a name/value pair?

that seems cool. and its a scalar so it can still be treated like a single string or number

therefore `{a=5} + {b=3} =` is this {a=8} or {b=8} or {0=8}? (last one?) 

A literal like 33 is really {0=33}. It can be iterated as a single value, but works with functions that take a single {Number} field.

remember, dot as a separator isn’t great since it means float cannot be used as an index. unless it is quoted in brackets?  struct.{1.23}.min

So the statement

`a=5` is the same as `5` same as `{5}` or `{a=5}` or `a={5}` . therefore they can all 

and `a={2+3}` is the same but evaluated lazily? So a literal `2+3` is also evaluated lazy

this means all expressions are lazy? what about more extensive method calling

So `{5-12} .Math.abs` is similar to `{0={5-12} .Math.abs}` , which would be lazy. Some concept like constexpr allows these to be computed at compile time.

For type coercion. How to define something like `{1,2}` can become `point{x=num,y=num)`? How implicitly is that done? what if I have a 3dpoint {x,y,z}. Want ways that only the defined fields are copied, probably never want additional fields. but a decision of if extras are ignored or failures.

For function definitions, how to define what type of structure a function takes. This feels super similar.

Also consider how a struct loaded from json data is converted into valid types. for example can I `.json.load` and immediately start calling methods on it for whichever type that is? Or do I need to pass it to the type constructor first.

```jsx
define record {first=String, last=String, age=Number?, **, full="{first} + {last}"}
function record.sendmail {...}

'record.json' .Json.load .record.sendmail
'record.json' .Json.load record .sendmail

{'joe', 'blow', 12} record >>full   # extract full name?
record {'f', 'l'}                   # or put type before? NO
```

so `"string" type` is how you build a type from another string. and since the string is lazy it could be `{"pre" + "post"} type` is there a way for a func to get the unevaluated block? iterate them. Could be interesting to get the block and check its context, or define a different context to evaluate the block in. (remember that the arg should be unmodifiable so this would create a new block to iterate)

So `>>` iterates a value from a struct. Does `>>=name` get a specific field? Have `<<` append a value to an iterator. `<< name=val` appends a field. Something like `<<<` to extend an iterator with a structs values (instead of the struct itself). Appending seems very much like modifying a structure, which generally seems avoidable. So that only can apply to a structure being built or local inside a function. 

Want a point constructor that can build from a 2 item struct or a struct with x,y defined values. how does this look? Perhaps allow python style ** to determine named or positional args?

```jsx
define point {
	x=Number
	y=Number
}
```

I guess any struct has a positional ordering based on the field definitions. What if another struct has “a” and “b” fields. can it become a point? seems so if it has two numbers.

Seeming like the function to build a type is different than the definition. Or perhaps the struct definition takes two blocks? One to define fields and ordering. One to define custom code to execute? If the data for any field can be defined as a block that is lazily run then maybe there is no need for a separate block?

If so, what is the difference between a function and a type? Feeling possible to combine into one thing.