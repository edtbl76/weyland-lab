//! Hello-world fixture for the Rust lane (B88).

/// Returns the fixture greeting.
pub fn hello() -> &'static str {
    "hello, weyland"
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Proves the Rust lane runs: toolchain, cargo, the built-in test harness.
    #[test]
    fn hello_returns_greeting() {
        assert_eq!(hello(), "hello, weyland");
    }

    /// Run ONLY by `run-lang-tests.sh rust --self-check` (`cargo test -- --ignored`).
    /// `#[ignore]` is what keeps a normal `cargo test` from collecting it, so the fixture passes
    /// normally while still proving the lane can fail.
    #[test]
    #[ignore]
    fn deliberate_failure() {
        panic!("deliberate: this failure is the point");
    }
}
