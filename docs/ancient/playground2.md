# playground2

```jsx
use Pygame

settings= {width=800 height=600 fullscreen=true}
window= settings .Pygame\window
{window, '#ccc'} .window\fill 

img = 'star.png' .Pygame\image\load
{window, img, pos={200,200}} .Pygame\image\blit

while event .Pygame\event\poll {
    if ?event..quit {
	    .Pygame\quit
```

was thinking creating an anon struct would have optional brackets, but for now see if required keeps things clearer.

was thinking space between struct and call was required. it could be optional but leave as required for readability and consistency

if and while condition don’t feel quite right

backslash isn’t awful, but forward slash would be so keen. what else makes a division? pipe|?

remove duplicates

```jsx
data= "numbers.json" .Io.readfile .Json.parse
function uniq { 
  _prev= {}
	for num {arg} {
		if num!=prev {
			_append=num
	}
	_prev= num
}
```

send email

```jsx
use Smtp
server= {'smtp.gmail.com', 587} .Smtp.server
{'username', 'password'} .server.login
msg= 'hello, mail'
msg .server.send
```

webapp

```jsx
use Fastapi

function index {
    hello='world'
}

{'get', ''} .Fastapi.call {
	hello='world'
}
```