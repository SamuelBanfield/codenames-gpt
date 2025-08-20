'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

type PlayerCtx = {
  playerId: string | null;
  setPlayerId: (id: string) => void;
};

const Ctx = createContext<PlayerCtx>({
  playerId: null,
  setPlayerId: () => {},
});

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const [playerId, _setPlayerId] = useState<string | null>(null);

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem('playerId') : null;
    if (saved) _setPlayerId(saved);
  }, []);

  const setPlayerId = (id: string) => {
    _setPlayerId(id);
    localStorage.setItem('playerId', id);
  };

  return <Ctx.Provider value={{ playerId, setPlayerId }}>{children}</Ctx.Provider>;
}

export const usePlayer = () => useContext(Ctx);
