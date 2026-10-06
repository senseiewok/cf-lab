# Twin of bad-psl010: two paths positionally, by name, and one from the pipeline.
$p = Join-Path 'a' 'b'
$q = Join-Path -Path 'a' -ChildPath 'b'
$r = 'a' | Join-Path -ChildPath 'b'
