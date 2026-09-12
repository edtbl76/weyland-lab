#!/usr/bin/env perl

# Deliberately-failing test — proves the perl lane PROPAGATES failure.
# It lives OUTSIDE t/, so a normal `prove -l` (which runs only t/) never sees it and stays green.
# The lane self-check runs `prove -l selfcheck/`, which executes this file and exits non-zero.
use Mojo::Base -strict;
use Test::More;

fail('selfcheck: the golden-path perl lane must surface this failure (exit non-zero)');

done_testing();
