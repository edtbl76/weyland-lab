# Flow: Media lane — image · TTS · video (B111)

Multimodal generation through Bifrost, all OpenAI-shaped: image (Runware), TTS (self-hosted Kokoro, the $0 primary),
and video (Runway — async submit then poll). One caller, the `/v1/...` verbs it already knows.

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller
    participant B as Bifrost /v1
    participant P as Provider
    C->>B: POST /v1/images/generations {model runware, prompt}
    B->>P: Runware
    P-->>B: image URL
    B-->>C: 200 {image URL}
    C->>B: POST /v1/audio/speech {model kokoro/kokoro, voice, input}
    B->>P: Kokoro-FastAPI (self-hosted, CPU)
    P-->>B: audio bytes
    B-->>C: 200 audio
    C->>B: POST /v1/videos {model gen4_turbo, prompt, input_reference}
    B->>P: Runway (Replicate tried first, then falls back)
    B-->>C: 200 {id, status queued}
    loop until completed (~30-90s)
        C->>B: GET /v1/videos/{id}
        B-->>C: status queued or completed
    end
    B-->>C: completed {videos with .mp4 URL}
```

Demo: [demos/media-lane.md](../demos/media-lane.md). Loadout: [design/bifrost-provider-loadout.md](../design/bifrost-provider-loadout.md).
