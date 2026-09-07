import { Address } from "@graphprotocol/graph-ts";

import { Reward, Visit } from "../generated/schema";
import {
  RewardPaid,
  VisitRecorded,
} from "../generated/VisitRegistry/VisitRegistry";
import {
  NO_MERCHANT,
  eventKey,
  firstTimeHere,
  loadCampaign,
  loadCampaignHour,
  loadMerchant,
  loadVisitor,
} from "./helpers";

export function handleVisitRecorded(event: VisitRecorded): void {
  const timestamp = event.block.timestamp;
  const visitor = loadVisitor(event.params.visitor, timestamp);

  // The event carries the campaign, not the merchant, so the owner comes from
  // the campaign itself. Copying it onto Visit is what lets the store
  // leaderboard sort without walking every campaign first.
  const campaign = loadCampaign(event.params.campaignId, NO_MERCHANT, timestamp);
  const merchant = loadMerchant(Address.fromBytes(campaign.merchant), timestamp);

  const visit = new Visit(eventKey(event.transaction.hash, event.logIndex));
  visit.campaign = campaign.id;
  visit.visitor = visitor.id;
  visit.merchant = merchant.id;
  visit.nullifierHash = event.params.nullifierHash;
  visit.sigHash = event.params.sigHash;
  visit.zone = campaign.zone;
  visit.timestamp = timestamp;
  visit.blockNumber = event.block.number;
  visit.transactionHash = event.transaction.hash;
  visit.save();

  if (firstTimeHere(visitor, merchant, timestamp)) {
    visitor.distinctMerchants = visitor.distinctMerchants + 1;
  }
  if (visitor.nullifierHash === null) {
    visitor.nullifierHash = event.params.nullifierHash;
  }
  visitor.visitCount = visitor.visitCount + 1;
  visitor.save();

  merchant.visitCount = merchant.visitCount + 1;
  merchant.save();

  campaign.visitCount = campaign.visitCount + 1;
  campaign.save();

  const bucket = loadCampaignHour(campaign, timestamp);
  bucket.visits = bucket.visits + 1;
  bucket.save();
}

export function handleRewardPaid(event: RewardPaid): void {
  const timestamp = event.block.timestamp;
  const visitor = loadVisitor(event.params.visitor, timestamp);
  const campaign = loadCampaign(event.params.campaignId, NO_MERCHANT, timestamp);

  const reward = new Reward(eventKey(event.transaction.hash, event.logIndex));
  reward.campaign = campaign.id;
  reward.visitor = visitor.id;
  reward.amount = event.params.amount;
  reward.timestamp = timestamp;
  reward.transactionHash = event.transaction.hash;
  reward.save();

  visitor.totalEarned = visitor.totalEarned.plus(event.params.amount);
  visitor.save();

  campaign.totalPaid = campaign.totalPaid.plus(event.params.amount);
  campaign.balance = campaign.balance.minus(event.params.amount);
  campaign.save();

  const merchant = loadMerchant(Address.fromBytes(campaign.merchant), timestamp);
  merchant.totalPaid = merchant.totalPaid.plus(event.params.amount);
  merchant.save();

  const bucket = loadCampaignHour(campaign, timestamp);
  bucket.paid = bucket.paid.plus(event.params.amount);
  bucket.save();
}
