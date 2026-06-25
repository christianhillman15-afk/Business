import Link from "next/link";

export const metadata = { title: "Privacy Policy — LeadPilot" };

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link href="/login" className="text-sm text-brand-600 hover:underline">
        ← Back
      </Link>
      <h1 className="mt-4 text-3xl font-bold">Privacy Policy</h1>
      <p className="mt-2 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
        Template — review with a lawyer before launch. This placeholder exists so
        the product has a linkable Privacy Policy; it is not legal advice.
      </p>

      <div className="prose mt-6 space-y-4 text-sm leading-6 text-slate-700">
        <h2 className="text-lg font-semibold">What we collect</h2>
        <p>
          Account details you provide (business name, email, phone, Nextdoor
          handle), your service/pricing settings, connected-account authorization
          tokens, the leads and replies generated for you, and support messages.
        </p>

        <h2 className="text-lg font-semibold">How we use it</h2>
        <p>
          To run the service: discover relevant leads, draft and publish content
          you approve, process billing, send transactional notifications, and
          provide support.
        </p>

        <h2 className="text-lg font-semibold">How it&apos;s protected</h2>
        <p>
          Passwords are hashed (Argon2id) and connected-account tokens are
          encrypted at rest (AES-256). Access is restricted by role.
        </p>

        <h2 className="text-lg font-semibold">Third parties</h2>
        <p>
          We use service providers to operate LeadPilot — for example a payment
          processor (Stripe), an email provider, an AI provider for drafting, and
          the social platforms you connect. We do not sell your personal data.
        </p>

        <h2 className="text-lg font-semibold">Your choices</h2>
        <p>
          You can edit your profile, disconnect accounts, and delete your account
          and associated data at any time from Settings. Requests:
          privacy@leadpilot.app
        </p>
      </div>

      <p className="mt-8 text-sm text-slate-500">
        See also our{" "}
        <Link href="/terms" className="text-brand-600 hover:underline">
          Terms of Service
        </Link>
        .
      </p>
    </div>
  );
}
