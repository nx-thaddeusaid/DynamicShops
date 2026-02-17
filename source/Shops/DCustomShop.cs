using BattleTech;
using BattleTech.UI;
using CustomShops;
using HBS;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using c = CustomShops.Control;

namespace DynamicShops.Shops;

public class DCustomShop : TaggedShop, ITextIcon, IDiscountFromFaction
{
    public DCustomShopDescriptor Descriptor { get; private set; }

    public override bool CanUse => UseConditions == null ||
                                   UseConditions.All(i => i.IfApply(c.State.Sim, c.State.CurrentSystem));
    public override bool Exists => ExistsConditions == null ||
                                   ExistsConditions.All(i => i.IfApply(c.State.Sim, c.State.CurrentSystem));

    public override int SortOrder => Descriptor.SortOrder;
    public override bool RefreshOnSystemChange => true;
    public override bool RefreshOnMonthChange => true;
    public override bool RefreshOnOwnerChange => false;

    protected override void UpdateTags()
    {
        List<string> tags = new List<string>();

        // Skip if no shops of given type exists
        if (!Control.CustomShopDefs.ContainsKey(Name))
            return;

        // Get list of shop defs with given custom name
        List<DCustomShopDef> defs = Control.CustomShopDefs[Name];

        foreach (var shop_def in defs)
        {
            Control.LogDebug(DInfo.Conditions, $"Start to check conditions:");

            var use = true;
            if (shop_def.Conditions != null)
            {
                foreach (var condition in shop_def.Conditions)
                {
                    Control.LogDebug(DInfo.Conditions, $"- {condition.GetType()}");
                    if (!condition.IfApply(c.State.Sim, c.State.CurrentSystem))
                    {
                        use = false;
                        break;
                    }
                }
            }
            else
            {
                Control.LogDebug(DInfo.Conditions, $"- empty");
            }
            if (use)
            {
                Control.LogDebug(DInfo.Conditions, DebugTools.ShowList("passed", shop_def.Items));
                tags.AddRange(shop_def.Items);
            }
        }           
        Tags = tags;
    }

    // public int GetPrice(TypedShopDefItem item) => PriceHelpers.GetPrice(item);

    public override string Name => Descriptor.Name;
    public override string TabText => Descriptor.TabText;

    public override string ShopPanelImage => SG_Stores_StoreImagePanel.STORE_ILLUSTRATION;

    public override Color IconColor => Color.white;
    public override Color ShopColor => LazySingletonBehavior<UIManager>.Instance.UILookAndColorConstants.SystemStoreColor.color;

    public List<DCondition> UseConditions => Descriptor.UseConditions;
    public List<DCondition> ExistsConditions => Descriptor.ExistConditions;

    public virtual string SpriteID
    {
        get
        {
            if (string.IsNullOrEmpty(Descriptor.Icon))
            {
                return "uixSvgIcon_ammoBox_Ballistic";
            }

            return Descriptor.Icon;
        }
    }

    public FactionValue RelatedFaction => c.State.CurrentSystem.OwnerValue;

    public DCustomShop(DCustomShopDescriptor decriptor)
    {
        Descriptor = decriptor;
    }
}