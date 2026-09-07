import { Address, BigInt, ByteArray, Bytes } from "@graphprotocol/graph-ts";

import {
  Campaign,
  CampaignHour,
  Merchant,
  Visitor,
  VisitorMerchant,
} from "../generated/schema";

export const ZERO = BigInt.fromI32(0);
export const HOUR = BigInt.fromI32(3600);
export const NO_MERCHANT = Address.zero();

// Six characters of geohash: a cell about 1200 x 600 metres. Small enough
// that being first in your zone is something a person can actually do, and it
// needs no map data — the zone is already inside the campaign's geohash.
export const ZONE_PRECISION = 6;

/**
 * Zone of a bytes32 geohash. The chain stores ASCII right-padded with zeros,
 * so this reads characters until the padding starts. An unset geohash — a
 * campaign we only ever saw funded, never created — gives an empty zone
 * rather than a wrong one.
 */
export function zoneOf(geohash: Bytes): string {
  let out = "";
  for (let i = 0; i < ZONE_PRECISION; i++) {
    if (i >= geohash.length || geohash[i] == 0) {
      return "";
    }
    out += String.fromCharCode(geohash[i]);
  }
  return out;
}

export function campaignKey(campaignId: BigInt): Bytes {
  return Bytes.fromByteArray(ByteArray.fromBigInt(campaignId));
}

export function eventKey(txHash: Bytes, logIndex: BigInt): Bytes {
  return txHash.concatI32(logIndex.toI32());
}

export function loadMerchant(address: Address, timestamp: BigInt): Merchant {
  let merchant = Merchant.load(address);
  if (merchant == null) {
    merchant = new Merchant(address);
    merchant.visitCount = 0;
    merchant.totalPaid = ZERO;
    merchant.firstSeenAt = timestamp;
    merchant.save();
  }
  return merchant;
}

export function loadVisitor(address: Address, timestamp: BigInt): Visitor {
  let visitor = Visitor.load(address);
  if (visitor == null) {
    visitor = new Visitor(address);
    visitor.visitCount = 0;
    visitor.distinctMerchants = 0;
    visitor.totalEarned = ZERO;
    visitor.firstSeenAt = timestamp;
    visitor.save();
  }
  return visitor;
}

/**
 * A campaign should be born from CampaignCreated. The contract does not emit
 * that event yet, so we create a shell the first time a campaign is mentioned
 * and fill in what the event carries. Reward, cap, radius, geohash and zone
 * keep their empty defaults: visibly missing rather than quietly wrong.
 *
 * `merchant` is Address.zero() when the event does not name one — VisitRecorded
 * carries only the campaign, so the owner is whatever CampaignFunded recorded.
 */
export function loadCampaign(
  campaignId: BigInt,
  merchant: Address,
  timestamp: BigInt
): Campaign {
  const key = campaignKey(campaignId);
  let campaign = Campaign.load(key);

  if (campaign == null) {
    campaign = new Campaign(key);
    campaign.campaignId = campaignId;
    campaign.merchant = loadMerchant(merchant, timestamp).id;
    campaign.rewardPerVisit = ZERO;
    campaign.dailyCap = 0;
    campaign.geohash = Bytes.empty();
    // A campaign with no zone stays out of the zone leaderboard instead of
    // being dropped into the wrong one.
    campaign.zone = "";
    campaign.radiusMeters = 0;
    campaign.balance = ZERO;
    campaign.active = true;
    campaign.createdAt = timestamp;
    campaign.visitCount = 0;
    campaign.totalPaid = ZERO;
    campaign.save();
  } else if (
    merchant != NO_MERCHANT &&
    campaign.merchant.equals(Bytes.fromHexString(NO_MERCHANT.toHexString()))
  ) {
    // The shell was created by a visit before we knew who owned it.
    campaign.merchant = loadMerchant(merchant, timestamp).id;
    campaign.save();
  }

  return campaign;
}

/**
 * Records that this wallet has been to this store, and answers whether it is
 * the first time. That answer is what the discovery bonus pays for, and it is
 * impossible to compute without an index of the chain.
 */
export function firstTimeHere(
  visitor: Visitor,
  merchant: Merchant,
  timestamp: BigInt
): boolean {
  const key = visitor.id.concat(merchant.id);
  let pair = VisitorMerchant.load(key);

  if (pair == null) {
    pair = new VisitorMerchant(key);
    pair.visitor = visitor.id;
    pair.merchant = merchant.id;
    pair.visits = 1;
    pair.firstVisitAt = timestamp;
    pair.save();
    return true;
  }

  pair.visits = pair.visits + 1;
  pair.save();
  return false;
}

/**
 * Hourly buckets, so the merchant panel never sums in the browser.
 */
export function loadCampaignHour(
  campaign: Campaign,
  timestamp: BigInt
): CampaignHour {
  const start = timestamp.div(HOUR).times(HOUR);
  const key = campaign.id.concatI32(start.toI32());
  let bucket = CampaignHour.load(key);
  if (bucket == null) {
    bucket = new CampaignHour(key);
    bucket.campaign = campaign.id;
    bucket.hourStart = start;
    bucket.visits = 0;
    bucket.paid = ZERO;
    bucket.save();
  }
  return bucket;
}
