# fastapi examples

setting a callback to a route feels like defining a function. a function that takes a ‘request’ struct in

```python
use FastApi

app= {} FastApi.Api

'/' app.get req {
	{message= "Hello World"} FastApi.Response
```

automatically async because the results are iterated?

with a pydantic like struct

```python
define Item {
	name= String
	description= String?
	price= Number
	Tax= Number?
}

'/items/{item_id}' app.put req {
   {item_id= req.query.item_id item=req.body Item}
 }
```

items in struct should use cue-like syntax to define types, validations. does it provide docs too?

functions that somehow accept a block get it passed AFTER the method to work like `for arg {}`