import { Address, BigInt, ByteArray, Bytes } from "@graphprotocol/graph-ts";

import {
  Campaign,
  CampaignHour,
  Merchant,
  MerchantWeek,
  Visitor,
  VisitorMerchant,
  VisitorWeek,
} from "../generated/schema";

export const ZERO = BigInt.fromI32(0);
export const HOUR = BigInt.fromI32(3600);
export const DAY = BigInt.fromI32(86400);
export const WEEK = BigInt.fromI32(604800);
export const NO_MERCHANT = Address.zero();

// Points. Five for showing up, five more the first time at that store, and
// nothing at all for a second visit to the same store on the same day.
export const POINTS_PER_VISIT = 5;
export const POINTS_NEW_MERCHANT = 5;

// The unix epoch fell on a Thursday, so a plain division puts week boundaries
// on Thursdays. Monday is three days earlier, and adding S before dividing
// moves every boundary S earlier — so three days lands them on Monday 00:00
// UTC, which is what a person means by "this week".
const MONDAY_SHIFT = BigInt.fromI32(259200);

export function weekStartOf(timestamp: BigInt): BigInt {
  return timestamp
    .plus(MONDAY_SHIFT)
    .div(WEEK)
    .times(WEEK)
    .minus(MONDAY_SHIFT);
}

export function dayOf(timestamp: BigInt): BigInt {
  return timestamp.div(DAY);
}

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
    visitor.points = 0;
    visitor.totalEarned = ZERO;
    visitor.firstSeenAt = timestamp;
    visitor.save();
  }
  return visitor;
}

/**
 * A campaign is born from CampaignCreated. A shell is still created when some
 * other event mentions a campaign first — events within a block are handled in
 * log order, but nothing guarantees we started indexing before the creation.
 * Reward, cap, radius, geohash and zone keep their empty defaults in that case:
 * visibly missing rather than quietly wrong.
 *
 * `merchant` is Address.zero() when the event does not name one — VisitRecorded
 * and the pause events carry only the campaign, so the owner is whatever
 * CampaignCreated or CampaignFunded recorded.
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
 * What a visit is worth, and whether the store is new to this wallet.
 *
 * Returns [points, isNewMerchant]. Ten the first time at a store, five on a
 * later day, nothing for coming back the same day — that last rule is why the
 * pair records the day it last scored, and it is what stops someone farming a
 * single counter all afternoon.
 */
export function scoreVisit(
  visitor: Visitor,
  merchant: Merchant,
  timestamp: BigInt
): i32[] {
  const key = visitor.id.concat(merchant.id);
  const today = dayOf(timestamp);
  let pair = VisitorMerchant.load(key);

  if (pair == null) {
    pair = new VisitorMerchant(key);
    pair.visitor = visitor.id;
    pair.merchant = merchant.id;
    pair.visits = 1;
    pair.firstVisitAt = timestamp;
    pair.lastScoredDay = today;
    pair.save();
    return [POINTS_PER_VISIT + POINTS_NEW_MERCHANT, 1];
  }

  pair.visits = pair.visits + 1;
  if (pair.lastScoredDay.equals(today)) {
    pair.save();
    return [0, 0];
  }

  pair.lastScoredDay = today;
  pair.save();
  return [POINTS_PER_VISIT, 0];
}

export function loadVisitorWeek(
  visitor: Visitor,
  timestamp: BigInt
): VisitorWeek {
  const start = weekStartOf(timestamp);
  const key = visitor.id.concatI32(start.toI32());
  let week = VisitorWeek.load(key);
  if (week == null) {
    week = new VisitorWeek(key);
    week.visitor = visitor.id;
    week.weekStart = start;
    week.points = 0;
    week.visits = 0;
    week.newMerchants = 0;
    week.save();
  }
  return week;
}

export function loadMerchantWeek(
  merchant: Merchant,
  timestamp: BigInt
): MerchantWeek {
  const start = weekStartOf(timestamp);
  const key = merchant.id.concatI32(start.toI32());
  let week = MerchantWeek.load(key);
  if (week == null) {
    week = new MerchantWeek(key);
    week.merchant = merchant.id;
    week.weekStart = start;
    week.visits = 0;
    week.paid = ZERO;
    week.save();
  }
  return week;
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
