# Fixture for PSL007: $matches is overwritten by every -match, so assigning to it is a bug.
if ('abc' -match 'b') { $matches = 5 }
