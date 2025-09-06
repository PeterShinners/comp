# nim examples

can only modify your own structures. something returned from a function.

there are stream objects which are iterators only and do not preserve their past values. these are one-time iterators.

```jsx
use Text
use Statistics

words = ctx.stdin .Text.streamlines .Text.streamwords

counts = {} .Statistics.counter
each words {word} {
	{counts, word} .Staticics.increment
	frequences.{word} = {frequencies.{word} | 0} + 1
}

most = counts .Statistics.greatest .struct.key
ctx.log("Most frequent word is {most}
```

feeling rough

much basic logic needs to be prepared ahead of time

want an easier way to iterate all words with a block that tallies words

there’s no good place for the `increment` and `greatest` calls. there’s no type to call methods from.

Maybe an operator to get an item by key instead of value. or actually want a ‘key’ type function?

```jsx
data .maximum  # biggest value
data ..maximim  # key with biggest value
data, key={i .absolute}  # want to call method on each iterated value

```