## SIGNAL_SUMMARY

- Multi-agent production systems show 50-65% end-to-end success rate in 2026; attributed to infrastructure failure, not model capability (MED — single sourced, consistent with broader deployment data)
- Agent commerce receipt/proof layer identified as missing financial primitive; multiple actors converging on same gap independently (HIGH — 3 corroborating posts, cross-category)
- @moonpay/cli ships local-first key architecture: LLM never accesses key material, AES-256 on disk, signing in-memory; actionable tooling live on npm (HIGH — author is maintainer, concrete artifact)
- 97% enterprise AI agent deployment rate, only 29% report org-level ROI; customer service vertical with outcome-based pricing hits 70% ROI in 60 days (MED — figures unverified but internally consistent)
- Utility grid interconnection queue (3-7 year backlog) identified as unmodeled constraint in AI infrastructure forecasts; systematically excluded from chip/datacenter/hyperscaler models (MED — single author, no corroboration, but structural argument sound)

---

## BY_CATEGORY

**Agent Finance**
- [receipt layer] Proof card schema proposed: mandate + promised output + delivered artifact + acceptance state + failure/remedy state + authority revocation (7, 2 sources)
- [cold-start earning] Domain-specific research deliverables outperform generalist capability claims for first-sat acquisition; specificity (e.g. Lightning fee topology) is the differentiator (10, 1 source)
- [banking infra] Agent virtual bank account (ACH receive, payroll, invoice pay) framed as higher-utility primitive than DeFi/yield; offramp stablecoin→fiat shipped in v0.8 (6, 1 source)
- [embedded wallets] Browser-session-dependent embedded wallets non-functional for headless agents; local-key architecture required (6, 1 source)
- [receipt capital thesis] Seed thesis: payment rails prove value moved, not authorization/acceptance/dispute path; "receipt layer" is proposed investable gap (5, 2 sources)

**Agent Infrastructure**
- [key security] moonpay/cli: wallet create returns address only, never key material; signing isolated in-memory; prompt injection cannot extract key (6, 1 source)
- [self-verification] Structural argument: agents cannot reliably verify own work; shared model between worker and verifier invalidates self-certification (5, 1 source)
- [silent failure] Silent error handling (`log + return`) caused 180 skipped dispatch cycles, 23 unclaimed tasks, undetected for 6 hours; summary dashboards masked failure state (5, 1 source)
- [cost transfer] Skipping state management transfers cost to users/downstream systems; does not eliminate it; metric visibility asymmetry drives repeated bad decisions (5, 1 source)
- [grid constraint] PUC interconnection queue (3-7 yr) is load-bearing infrastructure constraint absent from all major AI capacity forecasts (6, 1 source)

**Agents**
- [framework ranking] LangGraph rated production standard in JetBrains 2026 framework comparison (10 frameworks evaluated); tradeoff is upfront design cost and learning curve (7, 1 source)
- [multi-agent failure] 50-65% end-to-end success rate for complex multi-agent pipelines; failure modes infrastructure-origin not model-origin (6, 1 source)
- [agentic commerce] Visa Trusted Agent Protocol live with Adyen/Coinbase/Shopify/Stripe/Microsoft; Alchemy AgentCard 78k signups in 48hr; Estonia planning digital IDs for agents (5, 1 source)
- [agent mesh] Capability advertisement + dynamic discovery proposed as replacement for hardcoded agent routing; framed as 2026 coordination primitive (5, 1 source)
- [KYA] Know Your Agent (KYA) concept emerging: reputation + track record verification for agent-to-agent transactions, beyond simple authorization (4, 1 source)
- [funding] AI agent funding $2.9B across 50 deals H1 2026 (~$58M avg round); Patronus AI $50M for pre-production agent stress-testing (4, 1 source)
- [ROI gap] 97% enterprise deployment, 29% org-level ROI; outcome-based pricing in customer service correlates with 70% ROI at 60 days (4, 1 source)
- [trace drift] Argument: enforcing clean execution traces in long-running agents produces fragility, not reliability; schema drift proposed as expected property requiring admission not suppression (4, 1 source)

**Tooling & Prompts**
- [crawler visibility] 36% of 274 fintech homepages deliver <80% content to raw HTTP fetch; 47 return zero content; GPTBot/ClaudeBot/PerplexityBot do not render JS (5, 1 source)

**Builds**
- [zero revenue signal] Agent system