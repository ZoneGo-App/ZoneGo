import {
  CampaignCreated,
  CampaignFunded,
  CampaignPaused,
  CampaignUnpaused,
  CampaignWithdrawn,
} from "../generated/CampaignVault/CampaignVault";
import { loadCampaign, NO_MERCHANT, ZERO, zoneOf } from "./helpers";

/**
 * Where a campaign gets its reward, cap, radius and location.
 *
 * The contract emits this now, so a campaign arrives complete rather than
 * being discovered by its funding with empty values and no zone.
 */
export function handleCampaignCreated(event: CampaignCreated): void {
  const campaign = loadCampaign(
    event.params.campaignId,
    event.params.merchant,
    event.block.timestamp
  );

  campaign.rewardPerVisit = event.params.rewardPerVisit;
  campaign.dailyCap = event.params.dailyCap.toI32();
  campaign.geohash = event.params.geohash;
  campaign.zone = zoneOf(event.params.geohash);
  campaign.radiusMeters = event.params.radiusMeters.toI32();
  campaign.save();
}

export function handleCampaignFunded(event: CampaignFunded): void {
  const campaign = loadCampaign(
    event.params.campaignId,
    event.params.merchant,
    event.block.timestamp
  );

  campaign.balance = campaign.balance.plus(event.params.amount);
  campaign.save();
}

/**
 * The merchant takes their money back. `withdraw` empties the campaign in one
 * call — it does not take an amount — so the balance goes to zero rather than
 * being decremented, which also keeps this right if an event were ever missed.
 *
 * Without this handler the index kept reporting the funded balance forever,
 * and search offers whatever still looks funded. Somebody would have walked
 * fifteen minutes to a counter with nothing behind it.
 */
export function handleCampaignWithdrawn(event: CampaignWithdrawn): void {
  const campaign = loadCampaign(
    event.params.campaignId,
    event.params.merchant,
    event.block.timestamp
  );

  campaign.balance = ZERO;
  campaign.save();
}

/**
 * The merchant switches the campaign off — the shop is closed, the promotion
 * is over, they ran out of stock. The money stays in the vault, so balance is
 * untouched: this is the other half of "worth walking to", and the only half
 * the vault's balance cannot express.
 */
export function handleCampaignPaused(event: CampaignPaused): void {
  const campaign = loadCampaign(
    event.params.campaignId,
    NO_MERCHANT,
    event.block.timestamp
  );

  campaign.active = false;
  campaign.save();
}

export function handleCampaignUnpaused(event: CampaignUnpaused): void {
  const campaign = loadCampaign(
    event.params.campaignId,
    NO_MERCHANT,
    event.block.timestamp
  );

  campaign.active = true;
  campaign.save();
}
