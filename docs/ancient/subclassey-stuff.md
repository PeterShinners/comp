# Subclassy stuff

Back to the definition returning itself or a reference to a type. I think this could work with a single definition. Remember a single object is the same as a nested object. So `4` is `{4}` and a function that returns a single `{thing=val}` is the same as being that type (even if it is nested). This also means `{{{'name'}}} = 'name'`

The “shape” of a type knows if it is a scalar. These can also be iterated as a single value.

So how to define something like a subclass, as well as a method that takes args and gets overridden by subclass?

```python
define Pet {
	name: String
}

define PetTalkArg {pet:Pet count: Number & >=1 & help"The number of times to say"}

define Talk {PetTalkArg} arg {"unimplemented"}

define Cat {breed:String ..Pet}
define CatTalkArg {pet:Cat ..PetTalkArg}
define Talk {CatTalkArg} arg {"meow" * arg.count}
# or something like {1..arg.count i {"meow"}}

define Dog {..Pet}
define DotTalkArg {pet: Dog ..PetTalkArg}
define Talk DogTalkArg} arg {"woof" * arg.count)
```

Wins I’d like to see. Overriding a method in a subclass keeps all its docs, defaults, ranges. Unless specifically overridden?

But this feels tiresome and miserable. Also, if another container like House {address: A pet: Pet}. How will code know if the [`house.pet`](http://house.pet) is a dog or cat. And how can it call the right method?

```python
{house.pet 3} Talk  # is it 'meow meow meow' or 'woof woof woof'?
```

Tricky, because perhaps a subclass doesn’t have the same shape as a base class. This seems to introduce the concept of `supershape` and `subshape`. Can a `Dog` type be treated as a `Pet` type without modifying data (just ignoring some fields). This may be ok, but it also means the base types and validations cannot be changed in a subtype, only added onto.

Perhaps the struct for a call can be referenced through the call, like `Talk.argshape` . Then it could be defined on the fly, and also referenced and shared by other calls

```python
define Talk {
	pet:Pet
	count:Number & >=1 & help='text
} arg {
	'unimplemented'
}

def Talk {
	pet:Dog
	..Talk.arg
}	arg {
  'woof' * arg.count
}
```

But this is getting confusing, there are two Talk funcs, and it isn’t clear which is being called? Does the language “find the most specific type”? That seems hard to reconcile (although could be a goal for compile time)

I like going back to having `Pet` and `Dog` structs and defining methods onto those. But in the case where another arg is needed that gets complicated.

Maybe this means extra arguments should be passed through the context. The hard part is then “what context values does a function access” may be challenging to know.

So polymorphism is seeming real hard. Given a base type, how do sub types define alternate behavior.

Remember, this is also wanting to lean towards the middleware concept, where the subtype can wrap around the base type like middleware. It has a ‘before’ and ‘after’ block that runs around the base implementation, and can ignore or alter the data the base implementation sees.

(Unrelated question, could a String just be a struct of unnamed characters? Something to explore…