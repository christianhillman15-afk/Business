"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getToken, Plan } from "@/lib/api";
import { MarketingFooter, MarketingNav } from "@/components/MarketingNav";

export default function Landing() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [plans, setPlans] = useState<Plan[]>([]);

  useEffect(() => {
    if (getToken()) {
      router.replace("/dashboard");
      return;
    }
    setReady(true);
    api.get<Plan[]>("/api/plans").then(setPlans).catch(() => {});
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#070b1a] text-slate-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="bg-white">
      <div className="hero-bg text-white">
        <MarketingNav dark />

        {/* Hero */}
        <section className="section grid items-center gap-12 py-20 lg:grid-cols-2 lg:py-28">
          <div>
            <span className="eyebrow">⚡ AI lead-gen for local pros</span>
            <h1 className="mt-5 text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
              We do <span className="text-grad">everything</span>.
              <br />
              You just show up and get paid.
            </h1>
            <p className="mt-6 max-w-xl text-lg text-slate-300">
              Right now someone three streets over is asking for a{" "}
              <span className="font-semibold text-white">plumber</span>,{" "}
              <span className="font-semibold text-white">cleaner</span>, or{" "}
              <span className="font-semibold text-white">landscaper</span> — and
              your competitor is about to answer. LeadPilot&apos;s AI finds them,
              writes the perfect reply, and posts it for you. Your phone rings
              while you work.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/start" className="btn-cta">
                Start free — a lead a day, on us →
              </Link>
              <Link
                href="#how"
                className="btn-lg border border-white/20 text-white hover:bg-white/10"
              >
                See how it works
              </Link>
            </div>
            <p className="mt-4 text-sm text-slate-400">
              No credit card. No password. Set up in 3 minutes.
            </p>
          </div>

          {/* Floating product mock */}
          <div className="relative">
            <div className="absolute -inset-4 rounded-3xl bg-gradient-to-tr from-indigo-500/20 to-fuchsia-500/20 blur-2xl" />
            <div className="relative rounded-2xl border border-white/10 bg-white p-5 text-slate-800 shadow-2xl">
              <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
                <span className="badge bg-brand-50 text-brand-700">Nextdoor</span>
                <span className="badge bg-green-100 text-green-700">94% match</span>
                <span>· Maple Heights</span>
              </div>
              <p className="text-sm">
                “Our water heater died this morning — anyone know a good plumber
                who can come today?? 😩”
              </p>
              <div className="mt-3 rounded-xl bg-slate-50 p-3">
                <div className="mb-1 text-xs font-semibold text-slate-500">
                  ✍️ AI drafted your reply
                </div>
                <p className="text-sm text-slate-700">
                  Hi! I&apos;m with Rivertown Plumbing — we do same-day water
                  heater repair &amp; replacement. Service call $89, installs from
                  $1,200. Call/text (555) 014-7788 and I&apos;ll get you hot water
                  back today.
                </p>
                <div className="mt-3 flex gap-2">
                  <span className="btn-primary !py-1.5 !text-xs">Approve &amp; post</span>
                  <span className="btn-ghost !py-1.5 !text-xs">Edit</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Social-proof strip */}
        <div className="border-y border-white/10 bg-white/5">
          <div className="section flex flex-wrap items-center justify-center gap-x-10 gap-y-3 py-5 text-sm text-slate-400">
            <span>🔧 Plumbers</span>
            <span>🧹 Cleaners</span>
            <span>🌳 Landscapers</span>
            <span>🎨 Painters</span>
            <span>🛠️ Handymen</span>
            <span className="font-semibold text-white">
              + every local service business
            </span>
          </div>
        </div>
      </div>

      {/* Problem / agitation */}
      <section className="section py-20 text-center">
        <h2 className="mx-auto max-w-3xl text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Lead sites sell the same lead to{" "}
          <span className="text-fuchsia-600">five of your competitors.</span>
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600">
          Meanwhile, your actual neighbors are posting “who do you recommend?”
          every single day — for free. The problem isn&apos;t demand. It&apos;s
          that you can&apos;t watch every feed all day. We can.
        </p>
      </section>

      {/* How it works */}
      <section id="how" className="bg-slate-50 py-20">
        <div className="section">
          <div className="text-center">
            <span className="text-sm font-semibold uppercase tracking-wider text-indigo-600">
              Done for you
            </span>
            <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
              You connect once. We handle the rest.
            </h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                n: "1",
                t: "Tell us your trade",
                d: "Your services, pricing, and area — once. Takes 3 minutes.",
                icon: "🧰",
              },
              {
                n: "2",
                t: "Our AI works 24/7",
                d: "It scans local Nextdoor & Facebook feeds, finds people asking for exactly what you do, and writes a natural, on-brand reply.",
                icon: "🤖",
              },
              {
                n: "3",
                t: "You cash in",
                d: "Approve with one tap (or let it run). Your name, pricing, and number land in front of ready-to-buy neighbors.",
                icon: "💰",
              },
            ].map((s) => (
              <div key={s.n} className="feature-card">
                <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-xl">
                  {s.icon}
                </div>
                <div className="text-xs font-bold text-indigo-600">STEP {s.n}</div>
                <h3 className="mt-1 text-lg font-bold text-slate-900">{s.t}</h3>
                <p className="mt-2 text-sm text-slate-600">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="section py-20">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            Everything a $4,000/mo marketing agency does.
            <br />
            <span className="text-grad-dark">Without the agency.</span>
          </h2>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              icon: "🎯",
              t: "Only your trade",
              d: "Smart AI matching means a plumber gets plumbing jobs — never wasted on the wrong leads.",
            },
            {
              icon: "✍️",
              t: "Writes the reply for you",
              d: "Natural, neighborly replies with your services, pricing, and phone number — no copy-paste templates.",
            },
            {
              icon: "📣",
              t: "Posts on Nextdoor & Facebook",
              d: "Reaches the platforms where your neighbors actually ask for recommendations.",
            },
            {
              icon: "🗞️",
              t: "Promotes you proactively",
              d: "AI-written Business Posts put your offer in front of nearby neighbors on a schedule.",
            },
            {
              icon: "🌙",
              t: "Runs while you sleep",
              d: "Set it and forget it. New leads show up on your dashboard every morning.",
            },
            {
              icon: "🛡️",
              t: "You stay in control",
              d: "Review and approve before anything posts, with daily limits that keep your accounts safe.",
            },
          ].map((f) => (
            <div key={f.t} className="feature-card">
              <div className="text-2xl">{f.icon}</div>
              <h3 className="mt-3 text-lg font-bold text-slate-900">{f.t}</h3>
              <p className="mt-2 text-sm text-slate-600">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Big statement band */}
      <section className="hero-bg py-20 text-center text-white">
        <div className="section">
          <h2 className="mx-auto max-w-3xl text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl">
            Stop chasing work.
            <br />
            <span className="text-grad">Let it come to you.</span>
          </h2>
          <Link href="/start" className="btn-cta mt-8">
            Start your free trial →
          </Link>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="section py-20">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            One job pays for the whole month.
          </h2>
          <p className="mt-3 text-lg text-slate-600">
            Priced by how many replies you want per day. Start with a 7-day free
            trial — one lead a day, on us.
          </p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {plans.map((p) => {
            const featured = p.code === "growth";
            return (
              <div
                key={p.code}
                className={`rounded-2xl border p-6 ${
                  featured
                    ? "border-indigo-500 bg-indigo-600 text-white shadow-xl shadow-indigo-500/20"
                    : "border-slate-200 bg-white"
                }`}
              >
                {featured && (
                  <div className="mb-2 inline-block rounded-full bg-white/20 px-2 py-0.5 text-xs font-bold">
                    Most popular
                  </div>
                )}
                <div
                  className={`text-sm font-semibold ${featured ? "text-indigo-100" : "text-slate-500"}`}
                >
                  {p.name}
                </div>
                <div className="mt-1 text-4xl font-extrabold">
                  ${p.price_monthly}
                  <span
                    className={`text-base font-normal ${featured ? "text-indigo-200" : "text-slate-400"}`}
                  >
                    /mo
                  </span>
                </div>
                <div
                  className={`mt-2 text-sm ${featured ? "text-indigo-100" : "text-slate-600"}`}
                >
                  {p.daily_post_quota} {p.daily_post_quota === 1 ? "reply" : "replies"}{" "}
                  / day
                </div>
                <Link
                  href="/start"
                  className={`mt-5 block rounded-xl px-4 py-2.5 text-center text-sm font-semibold ${
                    featured
                      ? "bg-white text-indigo-700 hover:bg-indigo-50"
                      : "bg-slate-900 text-white hover:bg-slate-800"
                  }`}
                >
                  Start free
                </Link>
              </div>
            );
          })}
        </div>
      </section>

      {/* Testimonial */}
      <section className="bg-slate-50 py-20">
        <div className="section max-w-3xl text-center">
          <div className="text-4xl">“</div>
          <p className="text-2xl font-semibold leading-snug text-slate-800">
            I booked three jobs my first week and never touched my phone until the
            calls came in. It genuinely feels like having a salesperson working
            around the clock.
          </p>
          <p className="mt-5 text-sm font-medium text-slate-500">
            — Illustrative example of the outcome LeadPilot is built to deliver
          </p>
        </div>
      </section>

      {/* Final CTA */}
      <section className="section py-20 text-center">
        <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Your next customer is posting right now.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-lg text-slate-600">
          Be the one who answers. Start free in 3 minutes — no card, no password.
        </p>
        <Link href="/start" className="btn-cta-dark mt-8">
          Claim your free trial →
        </Link>
      </section>

      <MarketingFooter />
    </div>
  );
}
