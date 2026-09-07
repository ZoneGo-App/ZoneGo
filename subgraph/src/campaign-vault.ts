import { CampaignFunded } from "../generated/CampaignVault/CampaignVault";
import { loadCampaign } from "./helpers";

export function handleCampaignFunded(event: CampaignFunded): void {
  // Until CampaignCreated exists, this is where the index learns who owns a
  // campaign. Funding is the one event that names the merchant.
  const campaign = loadCampaign(
    event.params.campaignId,
    event.params.merchant,
    event.block.timestamp
  );

  campaign.balance = campaign.balance.plus(event.params.amount);
  campaign.save();
}
