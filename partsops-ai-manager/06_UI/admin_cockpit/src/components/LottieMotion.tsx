import { DotLottieReact, type DotLottie } from '@lottiefiles/dotlottie-react';
import { useEffect, useState } from 'react';

const configuredSource = import.meta.env.VITE_LOTTIE_SRC?.trim() ?? '';
const isEnabled = import.meta.env.VITE_LOTTIE_ENABLED === 'true';

function isApprovedLocalAsset(source: string): boolean {
  return source.startsWith('/assets/lottie/')
    && source.endsWith('.lottie')
    && !source.includes('..');
}

export function LottieMotion() {
  const [reducedMotion, setReducedMotion] = useState(true);
  const [player, setPlayer] = useState<DotLottie | null>(null);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!player) return;
    if (reducedMotion) {
      player.pause();
      player.setFrame(0);
      return;
    }
    player.play();
  }, [player, reducedMotion]);

  if (!isEnabled || !isApprovedLocalAsset(configuredSource)) return null;

  return (
    <DotLottieReact
      aria-hidden="true"
      autoplay={!reducedMotion}
      className="h-7 w-7 shrink-0"
      dotLottieRefCallback={setPlayer}
      loop={!reducedMotion}
      renderConfig={{
        autoResize: true,
        devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
        freezeOnOffscreen: true,
      }}
      src={configuredSource}
      stateMachineConfig={{
        openUrlPolicy: {
          requireUserInteraction: true,
          whitelist: [],
        },
      }}
    />
  );
}
