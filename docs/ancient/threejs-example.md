# threejs example

It feels like nested calls should make surrounding brackets required. Otherwise if optional they immediately become required in any non-trivial scenario.

Let’s try porting a ‘hello world’ from threejs

```python
window:= windowFromDom
scene:= Three.Scene  # default constructor

cam:= {75, window.innerWidth/window.innerHeight, 0.1, 1000} Three.PerspectiveCamera
cam:= {position.z=4 ..cam}  # modify field by cloning object, also a nested attr

renderer:= {antialias=true clearColor='#000'} Three.WebGlRenderer
{renderer window.innerWidth, window.innerHeight} setSize

geometry:= {1 1 1} Three.BoxGeometry
material:= {color='#438'} Three.MeshBasicMaterial
cube:= {geometry material} Three.Mesh

{scene cube} add

render.requestAnimationFrame {
	cube:= {rotation.x+=.01 rotation.y+=.01, ..cube}  # needs to reassign in-place?
	renderer.render(scene, camera)
```

Thoughts

- The cube is referenced by the mesh,  modifying the cube rotation must be done in-place. Perhaps that what `:=` is, or some operator?
- Change constructor to `{Type, arg1, arg2} new` ? This makes it like the other method calls. With no args that becomes `{Point} new`?
- Modifying position requires modifying a sub-object. Maybe the `..cam` should come at the beginning?