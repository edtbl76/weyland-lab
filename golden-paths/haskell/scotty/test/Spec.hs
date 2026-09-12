{-# LANGUAGE OverloadedStrings #-}

-- | Golden-path contract self-test (Haskell/Scotty) — the lane probe + contract proof.
--
-- Two layers: (1) the PURE payload builders are asserted directly (order-independent
-- 'Value' equality — robust to aeson key ordering); (2) the live WAI 'Application' is
-- driven over Network.Wai.Test (via hspec-wai) to prove the routes wire the builders.
module Main (main) where

import           Data.Aeson           (Value, decode, object, (.=))
import qualified Data.ByteString      as BS
import qualified Data.ByteString.Char8 as BC
import qualified Data.ByteString.Lazy as LB
import           Data.IORef           (newIORef)
import           Data.Text            (Text)
import qualified Data.Text            as T
import           Network.HTTP.Types   (status200)
import           Test.Hspec
import           Test.Hspec.Wai

import           Lib                  (application, healthPayload, helloPayload,
                                       readyPayload, renderMetrics, serviceName)

-- Expected payload rebuilt independently of Lib, so the test pins the actual shape.
expectedHello :: Value
expectedHello =
  object
    [ "service" .= ("golden-haskell-scotty" :: Text)
    , "message" .= ("hello, weyland" :: Text)
    ]

main :: IO ()
main = hspec $ do
  describe "pure payload builders" $ do
    it "healthPayload is {\"status\":\"ok\"}" $
      healthPayload `shouldBe` object ["status" .= ("ok" :: Text)]

    it "readyPayload is {\"status\":\"ready\"}" $
      readyPayload `shouldBe` object ["status" .= ("ready" :: Text)]

    it "helloPayload is the known contract payload" $
      helloPayload `shouldBe` expectedHello

    it "serviceName is golden-haskell-scotty" $
      serviceName `shouldBe` "golden-haskell-scotty"

    it "renderMetrics emits valid Prometheus text with the counter" $ do
      let out = renderMetrics 3
      out `shouldSatisfy` T.isInfixOf "# TYPE golden_hello_requests_total counter"
      out `shouldSatisfy` T.isInfixOf "golden_hello_requests_total 3"

  describe "live WAI application (the four contract endpoints)" $
    -- hspec-wai's `with` sets the item state to ((), Application) and rebuilds a
    -- fresh app (fresh counter IORef) per test — NOT Test.Hspec's `before`.
    with (newIORef 0 >>= application) $ do
      it "GET /health -> 200" $
        get "/health" `shouldRespondWith` 200

      it "GET /ready -> 200" $
        get "/ready" `shouldRespondWith` 200

      it "GET /hello -> 200 and decodes to the known payload" $ do
        resp <- get "/hello"
        liftIO $ decode (simpleBody resp) `shouldBe` Just expectedHello

      it "GET /metrics -> 200 and exposes the Prometheus counter" $ do
        resp <- get "/metrics"
        let body = LB.toStrict (simpleBody resp)
        liftIO $ do
          simpleStatus resp `shouldBe` status200
          (BC.pack "golden_hello_requests_total" `BS.isInfixOf` body)
            `shouldBe` True
