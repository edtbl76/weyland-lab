package GoldenPerlMojolicious;

# Golden path — Perl / Mojolicious (B164).
#
# The idiomatic Mojolicious full-app baseline. Runnable, ephemeral, extendable. Conforms to the
# golden-path contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
# Scaffold FROM it: scripts/new-service.sh perl/mojolicious <your-service>.
use Mojo::Base 'Mojolicious', -signatures;

our $SERVICE_NAME = 'golden-perl-mojolicious';

# Calls to the demo /hello endpoint. App-instance state so it survives across requests
# in one process (each Test::Mojo build gets a fresh app, which is what the tests expect).
sub startup ($self) {
    my $hello_hits = 0;

    my $r = $self->routes;

    $r->get(
        '/health' => sub ($c) {
            $c->render( json => { status => 'ok' } );
        }
    );

    $r->get(
        '/ready' => sub ($c) {
            $c->render( json => { status => 'ready' } );
        }
    );

    $r->get(
        '/hello' => sub ($c) {
            $hello_hits++;
            $c->render(
                json => { service => $SERVICE_NAME, message => 'hello, weyland' } );
        }
    );

    # Minimal-but-valid Prometheus text exposition (format version 0.0.4).
    $r->get(
        '/metrics' => sub ($c) {
            my $body = join(
                "\n",
                '# HELP golden_hello_requests_total Calls to the demo /hello endpoint',
                '# TYPE golden_hello_requests_total counter',
                "golden_hello_requests_total $hello_hits",
            ) . "\n";
            $c->res->headers->content_type('text/plain; version=0.0.4; charset=utf-8');
            $c->render( text => $body );
        }
    );

    $self->log->info(qq({"service":"$SERVICE_NAME","msg":"routes registered"}));
}

1;
