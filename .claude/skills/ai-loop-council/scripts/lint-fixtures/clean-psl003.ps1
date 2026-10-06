# Twin of bad-psl003: $script: only in a top-level function; the nested function does not use it.
$script:count = 0
function Bump {
    $script:count = $script:count + 1
}
function Outer {
    function Inner {
        $local = 1
        return $local
    }
    $null = Inner
}
Bump
