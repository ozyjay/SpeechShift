export type ShiftMode = "voice" | "language";

export interface VoiceOption {
  id: string;
  label: string;
  description: string;
  audio: string;
}

export interface LocalVoiceProfile {
  id: string;
  label: string;
  description: string;
}

export interface LanguageOption {
  id: string;
  label: string;
  text: string;
  audio: string;
}

export interface Sentence {
  id: string;
  prompt: string;
  source_text: string;
  original_audio: string;
  duration_ms: number;
  voices: VoiceOption[];
  languages: LanguageOption[];
}

export interface Catalogue {
  version: number;
  sentences: Sentence[];
}

export interface ProviderStatus {
  id: string;
  label: string;
  state: string;
  detail: string;
}

export interface PublicConfig {
  demo_name: string;
  demo_mode: string;
  provider: string;
  provider_label: string;
  audio_sample_rate: number;
  max_input_seconds: number;
  safe_output_volume: number;
  port_allocation_confirmed: boolean;
  providers: ProviderStatus[];
  local_voice_profiles: LocalVoiceProfile[];
}

export interface StreamEvent {
  type: string;
  sequence?: number;
  generation?: number;
  stage?: string;
  state?: string;
  text?: string;
  detail?: string;
  audio_url?: string;
  label?: string;
  autoplay?: boolean;
  first_audio_latency_ms?: number;
  replay_timing?: boolean;
  code?: string;
  mock?: boolean;
  dsp?: boolean;
  fixture?: boolean;
  mock_timing?: boolean;
  dsp_processing?: boolean;
  audio_format?: {
    encoding: string;
    sample_rate_hz: number;
    channels: number;
  };
}
