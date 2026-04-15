"""Inspect HuggingFace dataset structure without downloading."""

from datasets import load_dataset_builder, get_dataset_config_names

dataset_name = "th1nhng0/vietnamese-legal-documents"

print("=" * 60)
print(f"Dataset: {dataset_name}")
print("=" * 60)

# Get available configs
try:
    configs = get_dataset_config_names(dataset_name)
    print(f"\nAvailable configs: {configs}")
except Exception as e:
    print(f"\nError getting configs: {e}")

# Inspect each config
for config in configs:
    print(f"\n{'=' * 60}")
    print(f"Config: {config}")
    print("=" * 60)
    
    try:
        builder = load_dataset_builder(dataset_name, config)
        print(f"Description: {builder.info.description}")
        print(f"\nFeatures:")
        print(builder.info.features)
        print(f"\nDataset size: {builder.info.dataset_size}")
        print(f"Download size: {builder.info.download_size}")
        
        if builder.info.splits:
            print(f"\nSplits:")
            for split_name, split_info in builder.info.splits.items():
                print(f"  - {split_name}: {split_info.num_examples} examples")
    except Exception as e:
        print(f"Error inspecting config '{config}': {e}")
