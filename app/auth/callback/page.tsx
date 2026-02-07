import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { CallbackClient } from "./callback-client";

function Fallback() {
  return (
    <main className="min-h-screen bg-background text-white flex flex-col items-center justify-center gap-3">
      <Loader2 className="w-8 h-8 animate-spin text-primary" />
      <p className="text-sm text-gray-300">Preparing sign-in...</p>
    </main>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<Fallback />}>
      <CallbackClient />
    </Suspense>
  );
}
