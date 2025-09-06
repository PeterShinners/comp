# Examples v7

```python
makedirs = function # Create multiple levels of filesystem
arg {
	path: Path  # Full or relative path to create
	ctx.Filesystem ?= Std.Io.Filesystem # dependency for managing directories
}
body {
	runningpath = "/" Path
	for {token in arg.path.split}
		do {
			runningPath = {runningPath, token} Path.join
			if {not runningPath ctx.Filesystem.exists}
				do {
					runningPath ctx.Filesystem.makedir
				}
			}
		}
	}
	return.path = runningpath
}

ctx = StandardRuntimeContext()
{path="/tmp/subdir"} makedirs
```

Maybe `function` can known what variable/context it is being assigned into, so the function itself knows its name (based on this first assignment?) Maybe code can just know its name based on how/when it is called instead (cool?)

Need a way to iterate values that can get the “name”, “value” pair of a value. Sometimes name may be a placeholder, when dealing with a container of plain values. Feeling like that is just a different type than an object with named values.