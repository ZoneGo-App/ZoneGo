import {
  CampaignCreated,
  CampaignFunded,
} from "../generated/CampaignVault/CampaignVault";
import { loadCampaign, zoneOf } from "./helpers";

/**
 * Where a campaign actually gets its reward, cap, radius and location.
 *
 * The contract does not emit this yet — the ABI here matches the shape agreed
 * in schema/events.md, so the day Sebastian adds it nothing else changes.
 * Until then campaigns are discovered by their funding and carry empty values,
 * which is why they show no zone.
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
