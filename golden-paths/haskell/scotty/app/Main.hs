{-# LANGUAGE OverloadedStrings #-}

-- | Golden path — Haskell / Scotty. Runnable server: binds 0.0.0.0:8080 and serves the
-- contract mux. Structured JSON log line on startup; the counter is process-global.
module Main (main) where

import           Data.IORef                 (newIORef)
import qualified Data.Text                  as T
import qualified Data.Text.IO               as TIO
import           Network.Wai.Handler.Warp   (defaultSettings, setHost, setPort)
import           Web.Scotty                 (Options (..), scottyOpts)

import           Lib                        (routes, serviceName)

main :: IO ()
main = do
  counter <- newIORef 0
  -- setHost "*" binds all interfaces (0.0.0.0 + ::), setPort pins 8080.
  let opts =
        Options
          { verbose = 0
          , settings = setPort 8080 (setHost "*" defaultSettings)
          }
  TIO.putStrLn (T.concat ["{\"service\":\"", serviceName, "\",\"msg\":\"listening on :8080\"}"])
  scottyOpts opts (routes counter)
