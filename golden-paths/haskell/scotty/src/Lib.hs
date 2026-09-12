{-# LANGUAGE OverloadedStrings #-}

-- | Golden path — Haskell / Scotty (weyland B164).
--
-- The idiomatic Scotty baseline. Runnable, ephemeral, extendable. Conforms to the
-- golden-path contract (docs/design/golden-paths.md): GET \/health \/ready \/metrics \/hello.
-- Scaffold FROM it: scripts\/new-service.sh haskell\/scotty \<your-service\>.
--
-- The payload builders ('healthPayload', 'readyPayload', 'helloPayload', 'renderMetrics')
-- are PURE so the contract self-test drives them directly; 'application' wires them into a
-- WAI 'Application' the test exercises with Network.Wai.Test and @app\/Main.hs@ serves.
module Lib
  ( serviceName
  , healthPayload
  , readyPayload
  , helloPayload
  , renderMetrics
  , routes
  , application
  ) where

import           Control.Monad.IO.Class (liftIO)
import           Data.Aeson             (Value, object, (.=))
import           Data.IORef             (IORef, modifyIORef', readIORef)
import           Data.Text              (Text)
import qualified Data.Text              as T
import qualified Data.Text.Lazy         as TL
import           Network.Wai            (Application)
import           Web.Scotty             (ScottyM, get, json, scottyApp, setHeader, text)

-- | Stable service identity. The scaffolder rewrites this for a real service.
serviceName :: Text
serviceName = "golden-haskell-scotty"

-- | Liveness payload: @{"status":"ok"}@.
healthPayload :: Value
healthPayload = object ["status" .= ("ok" :: Text)]

-- | Readiness payload (the SMOKE-gate probe): @{"status":"ready"}@.
readyPayload :: Value
readyPayload = object ["status" .= ("ready" :: Text)]

-- | The known demo payload: @{"service":"golden-haskell-scotty","message":"hello, weyland"}@.
helloPayload :: Value
helloPayload =
  object
    [ "service" .= serviceName
    , "message" .= ("hello, weyland" :: Text)
    ]

-- | Minimal-but-valid Prometheus text exposition (format version 0.0.4) for the hello counter.
renderMetrics :: Int -> Text
renderMetrics hits =
  T.unlines
    [ "# HELP golden_hello_requests_total Calls to the demo /hello endpoint"
    , "# TYPE golden_hello_requests_total counter"
    , "golden_hello_requests_total " <> T.pack (show hits)
    ]

-- | The contract routes. @counter@ backs the /hello Prometheus counter.
routes :: IORef Int -> ScottyM ()
routes counter = do
  get "/health" $ json healthPayload
  get "/ready" $ json readyPayload
  get "/hello" $ do
    liftIO $ modifyIORef' counter (+ 1)
    json helloPayload
  get "/metrics" $ do
    hits <- liftIO $ readIORef counter
    setHeader "Content-Type" "text/plain; version=0.0.4; charset=utf-8"
    text (TL.fromStrict (renderMetrics hits))

-- | Build the WAI 'Application' (no live socket needed — the self-test drives it directly).
application :: IORef Int -> IO Application
application counter = scottyApp (routes counter)
