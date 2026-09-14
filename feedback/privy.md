# Feedback for Privy

Everything below comes from building ZoneGo, and points at the code it refers
to. The frontend lives under `frontend/ZoneGoApp/src/`.

## What we integrated

ZoneGo has two users who will never install a wallet: a store owner who pays for
visits, and a neighbour who is paid for making one. Privy gives both of them a
wallet without either knowing it.

- **An embedded wallet for every user on login.** `main.tsx` configures
  `PrivyProvider` with `embeddedWallets.ethereum.createOnLogin: 'all-users'`.
  There is no step where anyone creates, backs up or names a wallet.
- **Login by email, or SMS.** Merchants sign in with email; neighbours are
  offered SMS and email (`screens/Onboarding.tsx`).
- **The merchant moves money.** `screens/MerchantPanel.tsx` uses
  `useSendTransaction` twice: approve USDC for the campaign vault, then fund the
  campaign. That is how the live campaigns on Base Sepolia were funded.
- **The merchant signs every visit.** `screens/ScanQr.tsx` uses
  `useSignTypedData` for the EIP-712 `VisitSig` that `VisitRegistry` verifies on
  chain. The merchant's embedded wallet is the authority for which visit is
  real; our backend never signs one.
- **The neighbour is paid into their embedded wallet**, without ever holding
  gas: a relay submits the claim, and the contract pays the address the
  merchant's signature names.

We did not use organization wallets, policies, signers or key quorums.

In progress, not yet on the branch: a merchant signing their store's name and
description with `useSignMessage`, so the API accepts a profile only from the
wallet it describes.

## What worked well

- **`createOnLogin: 'all-users'`** is the whole onboarding. One line of config
  replaced what would otherwise be a wallet-creation screen for two
  non-technical audiences.
- **`useSendTransaction` and `useSignTypedData` take plain `{ to, data }` and
  EIP-712 objects.** Calldata encoded by hand for the vault went straight in, and
  the typed data our API returns is passed to the wallet without being rebuilt.

## What took longer than it should have

**SMS login only reaches the US and Canada, and a user finds out at the end.**
Two of our team are outside North America, and SMS login did not work for
either of them. The SDK's error screen for that case reads "This region is not
supported — SMS authentication from this region is not available", shown when
the API answers `NOT_SUPPORTED`. The docs do say it: "This enables SMS log
in for only US and Canada", with international SMS through BYO Twilio on the
Scale and Enterprise plans. But nothing in the login modal hints at it before
the number is typed. Showing SMS only where it works, or saying so beside the
field, would stop a first-time user hitting a dead end on their first screen.

**The production build needed Solana packages we do not use.** An
Ethereum-only app failed to build until `@solana-program/memo`,
`@solana-program/system`, `@solana-program/token` and `@solana/kit` were added
to `package.json` as dependencies (commit `068f5ba`). A note on which peer
dependencies an EVM-only integration can expect to need would have saved the
debugging.

## Documentation

### Issues already reported by others

- `docs.privy.io/recipes/send-usdc` has broken links to Circle's site for the
  USDC addresses, on both mainnet and testnets. Reported by another participant
  on Sept 4 in the ETHOnline Discord channel.

### Issues we found ourselves

| Date | What we did | What we expected | What happened |
|---|---|---|---|
| Sept 12 | Built the frontend for production with Privy and EVM wallets only | A build with no Solana dependencies | The build failed until four Solana packages were added as dependencies |
| Sept 13 | Logged in by SMS from outside North America | An SMS code, or a warning before choosing SMS | SMS login refused for the region; email worked |

## How Privy improves the product

Our product only works if two people who have never used crypto both use it:
the woman who runs the bodega, and the neighbour who walks in.

Without Privy, the merchant installs a wallet extension, saves a seed phrase,
buys gas and learns what an approval is before paying for her first visitor.
The neighbour does the same before earning five cents. Neither would.

With Privy, the merchant signs in with her email and funds a campaign in dollars
from a wallet she never created. When a neighbour reaches her counter, she
signs the visit from that same wallet. The neighbour signs in, walks, and is
paid into a wallet they never saw being made. Neither side meets a seed phrase,
a gas fee or the word "blockchain".

Where that stands: all of it has run on chain. The live campaigns were approved
and funded from embedded wallets, and before the submission deadline two visits were claimed
through the app — the merchant signing each one from their embedded wallet, the
neighbour paid 0.05 USDC per visit into theirs, without holding gas:

- https://sepolia.basescan.org/tx/0x8520f584c7581bc13193f44f3e11b1bf248a13edd71c1e37946ad01e5b9a8295
- https://sepolia.basescan.org/tx/0x99eacccae413246d43a3817b5dd3140d38a981d4a62f20378cd86db841660c34

---

**Privy contact:** @Coby | Privy (Discord)
