Changing block syntax to use dotted definitions after the function definition.

There is also an unnabled block allowed, which is referenced with a single `.`.
That may pose a syntax challenge and need changing?

```
!func :handle-request ~{url~str} = {
    $req = url -> :prepare_request

    -?? req.method == #GET -&& $req -> .get
    -|? req.method == #POST -&& $req -> .post
    -|| {#fail.value "Http method ${req.method} not supported"}
}
.get~{request} {#fail.value "Http method GET not implemented"}
.post~{request} {#fail.value "Http method POST not implemented"}
```

There are no more variadic blocks, but that could make a return if a
use case is presented.

Perhaps the unnamed block is defined and referenced as `.block` but
when invoked the base dotted syntax is allowed.