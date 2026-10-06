# Fixture for PSL003: three levels deep; the single $script: use is reported once, not once per enclosing function.
function A {
    function B {
        function C {
            $script:count = 1
        }
    }
}
