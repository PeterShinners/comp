# Units

Units provide semantic typing and automatic conversions for primitive values in Comp. They attach to numbers and strings using tag notation, creating typed values that maintain their meaning through operations and transformations.

Units are implemented as tag hierarchies with conversion rules and validation logic. For comprehensive information about the tag system underlying units, see [Tag System](tag.md).

## Number Units

Units provide semantic typing and automatic conversion for numeric values. They attach to numbers using tag notation, creating typed values that maintain their meaning through operations. Units are implemented as tag hierarchies with conversion rules.

```comp
; Units as tags
distance = 5#kilometer
duration = 30#second
temp = 20#celsius

; Automatic conversion in operations
total = 5#meter + 10#foot          ; Result in meters
speed = 100#kilometer / 1#hour     ; Compound unit

; Explicit conversion
meters = distance ~num#meter      ; 5000
feet = distance ~num#foot         ; ~16.404
kelvin = temp ~num#kelvin         ; 293.15
```

### Unit Rules

Units follow algebraic rules during mathematical operations:
- **Addition/subtraction require compatible units** - you can't add meters to seconds
- **First operand's unit determines result unit** - `5#meter + 10#foot` returns meters
- **Multiplication/division create compound units** - `100#kilometer / 1#hour` becomes `#kilometer-per-hour`
- **Incompatible operations fail immediately** - type errors at validation time, not runtime

### Unit Hierarchies

Units are organized in hierarchies that define conversion relationships:

```comp
; Distance units (example hierarchy)
#distance {
    #meter = 1
    #kilometer = 1000
    #centimeter = 0.01
    #millimeter = 0.001
    
    #foot = 0.3048
    #inch = 0.0254
    #mile = 1609.34
}

; Time units
#time {
    #second = 1
    #minute = 60
    #hour = 3600
    #day = 86400
    #week = 604800
}

; Temperature units (requires offset conversions)
#temperature {
    #kelvin = {scale=1 offset=0}
    #celsius = {scale=1 offset=273.15}
    #fahrenheit = {scale=0.5556 offset=255.37}
}
```

### Compound Units

Operations automatically create and simplify compound units:

```comp
; Speed from distance and time
distance = 100#kilometer
time = 2#hour
speed = distance / time           ; 50#kilometer-per-hour

; Force from mass and acceleration
mass = 10#kilogram
accel = 9.8#meter-per-second-squared
force = mass * accel              ; 98#newton (kilogram-meter-per-second-squared)

; Area from length multiplication
width = 5#meter
length = 10#meter
area = width * length             ; 50#meter-squared

; Unit cancellation
distance = 100#meter
speed = 10#meter-per-second
time = distance / speed           ; 10#second (meters cancel)
```

### Unit Validation

Unit type checking happens at shape validation time:

```comp
; Function with unit requirements
func calculate-speed ~{distance ~num#meter time ~num#second} = {
    [distance / time]  ; Result: ~num#meter-per-second
}

; Valid call
calculate-speed {distance=100#meter time=10#second}

; Automatic conversion
calculate-speed {distance=1#kilometer time=10#second}  ; kilometers converted to meters

; Incompatible units fail
calculate-speed {distance=100#meter time=5#kilogram}   ; ERROR: incompatible units
```

### Custom Unit Definitions

Define custom units with conversion rules:

```comp
; Define a custom unit hierarchy
!tag #pressure {
    #pascal = 1
    #kilopascal = 1000
    #bar = 100000
    #atmosphere = 101325
    #psi = 6894.76
}

; Use custom units
atmospheric = 1#atmosphere
tire-pressure = 32#psi
total = atmospheric + tire-pressure    ; Result in atmospheres
```

## String Units

String units attach to strings using tag notation, providing semantic meaning and controlling template behavior. Units can validate formats, apply transformations, and ensure proper escaping in templates.

```comp
; String with unit tag
email = "user@example.com"#email
query = "SELECT * FROM users WHERE id = %{id}"#sql
markup = "<h1>%{title}</h1>"#html

; Units affect template formatting
user-id = "; DROP TABLE users; -- "
safe-query = "SELECT * FROM users WHERE id = %{user-id}#sql" % {user-id}
; SQL unit ensures proper escaping: "SELECT * FROM users WHERE id = '; DROP TABLE users; --'"

; Unit validation
invalid = "not-an-email"#email       ; Fails validation
normalized = "USER@EXAMPLE.COM"#email ; Becomes lowercase: "user@example.com"
```

### Built-in String Units

Common string units are provided by the standard library:

```comp
; Email validation and normalization
email = "user@EXAMPLE.com"#email      ; Normalized to lowercase

; URL handling
url = "https://example.com/path"#url  ; Validates URL format
encoded = url | encode#url            ; URL-encodes for use in parameters

; Format-aware strings for templates
html = "<p>%{content}</p>"#html       ; HTML escaping in templates
sql = "WHERE name = '%{name}'"#sql    ; SQL escaping in templates
json = '{"key": "%{value}"}'#json     ; JSON escaping in templates
xml = "<tag>%{data}</tag>"#xml        ; XML escaping in templates

; Filesystem paths
path = "/home/user/file.txt"#path     ; Platform-aware path handling
relative = "../../data"#path          ; Relative path normalization
```

### String Unit Behavior in Templates

String units control how values are escaped when used in templates:

```comp
; HTML escaping
user-input = "<script>alert('xss')</script>"
safe-html = "<div>%{user-input}</div>"#html % {user-input}
; Result: "<div>&lt;script&gt;alert('xss')&lt;/script&gt;</div>"

; SQL escaping
user-name = "admin' OR '1'='1"
safe-query = "SELECT * FROM users WHERE name = '%{user-name}'"#sql % {user-name}
; Result: "SELECT * FROM users WHERE name = 'admin'' OR ''1''=''1'"

; JSON escaping
message = 'Hello "World"'
safe-json = '{"message": "%{message}"}'#json % {message}
; Result: '{"message": "Hello \"World\""}'
```

### Custom String Units

Define custom string units with validation and transformation rules:

```comp
; Custom string unit definition
!tag #url ~str {
    validate = |parse/url           ; Validation function
    normalize = |normalize/url      ; Normalization function
    escape = |encode/url            ; Escaping for templates
}

; Custom phone number unit
!tag #phone ~str {
    validate = :(it | match/str "^[0-9]{3}-[0-9]{3}-[0-9]{4}$")
    normalize = :(it | replace/str ["-" ""])
}

; Use custom units
valid-phone = "555-123-4567"#phone   ; Validates format
normalized = valid-phone             ; "5551234567" (dashes removed)

invalid-phone = "not-a-phone"#phone  ; Validation error
```

### Unit Composition

String units can be composed and transformed:

```comp
; Start with one unit
base-url = "https://example.com"#url

; Transform to different unit
path-part = "/api/users"#path
full-url = base-url | append#url path-part  ; Composes URLs properly

; Unit-aware concatenation
html-safe = "<p>Hello</p>"#html
more-html = "<p>World</p>"#html
combined = html-safe | concat#html more-html  ; Both parts remain HTML-safe
```

## Unit System Design

Units in Comp are:

1. **Type-safe**: Unit mismatches are caught at shape validation time
2. **Automatic**: Conversions happen transparently when needed
3. **Composable**: Units combine through arithmetic operations naturally
4. **Extensible**: Define custom units for domain-specific needs
5. **Zero-overhead**: Unit information is compile-time only, no runtime cost for validated code

Units transform error-prone manual conversions into automatic, validated operations that make code both safer and more readable.
