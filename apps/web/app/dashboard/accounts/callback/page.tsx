'use client';

import { Suspense, useEffect, useState } from 'react';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '../../../../lib/supabase/client';
import { bankAccountsApi } from '../../../../lib/api/client';

type Status = 'loading' | 'success' | 'rejected' | 'error';

function CallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<Status>('loading');
  const [message, setMessage] = useState('Processing consent…');

  useEffect(() => {
    const consentId = searchParams.get('consent_id') ?? searchParams.get('consentId');

    async function processConsent() {
      if (!consentId) {
        setStatus('error');
        setMessage('Missing consent_id in callback URL.');
        return;
      }

      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        router.replace('/login');
        return;
      }

      try {
        const result = await bankAccountsApi.handleCallback(consentId, session.access_token);
        if (result?.status === 'active') {
          setStatus('success');
          setMessage('Account linked successfully! Syncing transactions…');
          setTimeout(() => router.replace('/dashboard/accounts'), 2500);
        } else if (result?.status === 'rejected') {
          setStatus('rejected');
          setMessage('Consent was rejected. You can try linking again from the Accounts page.');
          setTimeout(() => router.replace('/dashboard/accounts'), 3000);
        } else {
          setStatus('success');
          setMessage(`Consent status: ${result?.status ?? 'unknown'}. Redirecting…`);
          setTimeout(() => router.replace('/dashboard/accounts'), 2500);
        }
      } catch {
        setStatus('error');
        setMessage('Something went wrong processing your consent. Please try again.');
      }
    }

    processConsent();
  }, [router, searchParams]);

  const icon =
    status === 'loading' ? (
      <Loader2 size={48} className="animate-spin text-primary" />
    ) : status === 'success' ? (
      <CheckCircle2 size={48} className="text-green-500" />
    ) : (
      <XCircle size={48} className="text-destructive" />
    );

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 text-center p-8">
      {icon}
      <div>
        <h1 className="text-xl font-bold">
          {status === 'loading'
            ? 'Linking Your Account'
            : status === 'success'
              ? 'Account Linked!'
              : status === 'rejected'
                ? 'Consent Declined'
                : 'Something Went Wrong'}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground max-w-sm">{message}</p>
      </div>
      {(status === 'error' || status === 'rejected') && (
        <button
          onClick={() => router.replace('/dashboard/accounts')}
          className="rounded-2xl bg-primary px-6 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-90 transition-opacity"
        >
          Back to Accounts
        </button>
      )}
    </div>
  );
}

export default function AccountCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center">
          <Loader2 size={48} className="animate-spin text-primary" />
        </div>
      }
    >
      <CallbackInner />
    </Suspense>
  );
}
