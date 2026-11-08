ALTER TABLE fee_type ADD COLUMN IF NOT EXISTS fee_group text;

UPDATE fee_type SET fee_group = 'commission'   WHERE type_id IN ('SUC','FSF');
UPDATE fee_type SET fee_group = 'shipping'     WHERE type_id IN
  ('HB4','DPB','HLB','DXP','DPA','ORB','HB2','HXO','PTR','HB1','DTR','DHR');
UPDATE fee_type SET fee_group = 'promotion'    WHERE type_id IN ('NSP','FE1','FEA');
UPDATE fee_type SET fee_group = 'subscription' WHERE type_id = 'SB2';
UPDATE fee_type SET fee_group = 'refund'       WHERE type_id IN ('REF','PS1');
UPDATE fee_type SET fee_group = 'technical'    WHERE type_id IN ('PAD','PB2','PBL','SUM');