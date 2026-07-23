"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { makeQueryClient } from "@/lib/query";

/**
 * Providers client de l'app — un QueryClient par arbre React (créé
 * paresseusement pour rester stable entre re-renders).
 */
export default function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
