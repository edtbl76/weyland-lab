-- | Deliberately-failing selfcheck — proves the Haskell lane PROPAGATES failure.
--
-- Gated OUT of a normal `cabal test` by the manual `selfcheck` cabal flag
-- (buildable: False unless -fselfcheck), so the everyday suite is green. The lane
-- self-check runs it explicitly:  cabal test selfcheck -fselfcheck
-- which builds + runs this and exits NON-ZERO.
module Main (main) where

import Test.Hspec

main :: IO ()
main = hspec $
  describe "selfcheck" $
    it "the golden-path Haskell lane must surface this failure (exit non-zero)" $
      expectationFailure "selfcheck: deliberate failure — the lane must propagate this (exit non-zero)"
