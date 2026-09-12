#!/usr/bin/env perl

# Golden-path self-test (Perl/Mojolicious) — the lane probe + contract proof.
# Test::Mojo drives the app in-process (no live socket), mirroring the go/dart exemplars.
use Mojo::Base -strict;
use Test::More;
use Test::Mojo;

my $t = Test::Mojo->new('GoldenPerlMojolicious');

# GET /health -> 200 {"status":"ok"}
$t->get_ok('/health')->status_is(200)->json_is( '/status' => 'ok' );

# GET /ready -> 200 {"status":"ready"}
$t->get_ok('/ready')->status_is(200)->json_is( '/status' => 'ready' );

# GET /hello -> 200 known payload
$t->get_ok('/hello')->status_is(200)
    ->json_is( '/service' => 'golden-perl-mojolicious' )
    ->json_is( '/message' => 'hello, weyland' );

# GET /metrics -> 200 Prometheus text exposition (counter reflects the /hello call above)
$t->get_ok('/metrics')->status_is(200)
    ->content_type_like(qr{text/plain})
    ->content_like(qr/golden_hello_requests_total/);

done_testing();
