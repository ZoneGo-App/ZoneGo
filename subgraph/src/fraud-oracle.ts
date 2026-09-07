import { ByteArray, Bytes } from "@graphprotocol/graph-ts";

import { Epoch } from "../generated/schema";
import { EpochCommitted } from "../generated/FraudOracle/FraudOracle";

export function handleEpochCommitted(event: EpochCommitted): void {
  // One entity per epoch, keyed by the epoch number, so a score published for
  // a given hour can be proved later and never rewritten.
  const key = Bytes.fromByteArray(
    ByteArray.fromBigInt(event.params.epoch)
  );

  const epoch = new Epoch(key);
  epoch.epoch = event.params.epoch;
  epoch.merkleRoot = event.params.root;
  epoch.timestamp = event.block.timestamp;
  epoch.save();
}
