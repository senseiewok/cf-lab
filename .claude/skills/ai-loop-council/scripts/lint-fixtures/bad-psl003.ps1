# Fixture for PSL003: $script: used inside a function defined inside another function.
function Outer {
    function Inner {
        $script:count = 1
    }
    Inner
}
Outer
