<?php
// Deliberately-failing test — proves the php lane PROPAGATES failure. It carries the PHPUnit
// `selfcheck` group; a normal run uses --exclude-group selfcheck and the lane self-check uses
// --group selfcheck (only it). Group-based (not a test-NAME filter): dropping the group makes it run
// in the NORMAL lane, which is loud, not silent.
declare(strict_types=1);

use PHPUnit\Framework\Attributes\Group;
use PHPUnit\Framework\TestCase;

final class DeliberateTest extends TestCase
{
    #[Group('selfcheck')]
    public function testDeliberateFailure(): void
    {
        self::fail('selfcheck: the golden-path php lane must surface this failure (exit non-zero)');
    }
}
