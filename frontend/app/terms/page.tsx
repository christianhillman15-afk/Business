import Link from "next/link";

export const metadata = { title: "Terms of Service — LeadPilot" };

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link href="/login" className="text-sm text-brand-600 hover:underline">
        ← Back
      </Link>
      <h1 className="mt-4 text-3xl font-bold">Terms of Service</h1>
      <p className="mt-2 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
        Template — review with a lawyer before launch. This placeholder exists so
        the product has linkable Terms; it is not legal advice.
      </p>

      <div className="prose mt-6 space-y-4 text-sm leading-6 text-slate-700">
        <h2 className="text-lg font-semibold">1. The service</h2>
        <p>
          LeadPilot helps local service businesses discover potential customers
          on community platforms and drafts replies for the user to review and
          publish. The user is responsible for the content they choose to post.
        </p>

        <h2 className="text-lg font-semibold">2. Acceptable use</h2>
        <p>
          You agree to use connected platforms in line with their terms. You will
          not use LeadPilot to post spam, operate fake or unauthorized accounts,
          evade platform restrictions, or send unsolicited messages in violation
          of applicable law (including CAN-SPAM and TCPA).
        </p>

        <h2 className="text-lg font-semibold">3. Accounts &amp; connections</h2>
        <p>
          You connect your own authorized social accounts via official
          authorization. You are responsible for activity on your account. We
          never request your platform passwords.
        </p>

        <h2 className="text-lg font-semibold">4. Billing &amp; trial</h2>
        <p>
          Paid plans are billed monthly. Free trials convert to a paid plan only
          if you choose one; otherwise access is limited when the trial ends. You
          can cancel at any time.
        </p>

        <h2 className="text-lg font-semibold">5. Disclaimers</h2>
        <p>
          The service is provided “as is.” We do not guarantee leads, results, or
          that any third-party platform will permit a given action. Platform
          access and rules are outside our control.
        </p>

        <h2 className="text-lg font-semibold">6. Contact</h2>
        <p>Questions about these terms: support@leadpilot.app</p>
      </div>

      <p className="mt-8 text-sm text-slate-500">
        See also our{" "}
        <Link href="/privacy" className="text-brand-600 hover:underline">
          Privacy Policy
        </Link>
        .
      </p>
    </div>
  );
}
