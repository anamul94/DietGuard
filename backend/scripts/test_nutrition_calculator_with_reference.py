"""
Test script for nutrition calculator agent with reference data.

This script tests the enhanced nutrition calculator agent that accepts
old food analysis as reference for maintaining calculation consistency.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from infrastructure.agents.nutrition_calculator_agent import nutrition_calculator_agent


async def test_without_reference():
    """Test nutrition calculation without reference data (baseline)"""
    print("=" * 60)
    print("TEST 1: Nutrition Calculation WITHOUT Reference Data")
    print("=" * 60)
    
    fooditems = [
        "raw salmon fillet",
        "chicken breast",
        "avocado cut in half"
    ]
    
    print(f"\nFood Items: {fooditems}")
    print("\nCalling agent...")
    
    response = await nutrition_calculator_agent(fooditems)
    
    if response.success:
        print("\n✓ Agent call successful!")
        print(f"\nResponse Data:")
        print(f"  Food Items: {response.data.get('fooditems', [])}")
        print(f"  Nutrition: {response.data.get('nutrition', {})}")
        
        if hasattr(response, 'metadata'):
            print(f"\nMetadata:")
            print(f"  Model: {response.metadata.get('model_name', 'unknown')}")
            print(f"  Input Tokens: {response.metadata.get('input_tokens', 0)}")
            print(f"  Output Tokens: {response.metadata.get('output_tokens', 0)}")
    else:
        print(f"\n✗ Agent call failed: {response.error_message}")
    
    return response


async def test_with_reference():
    """Test nutrition calculation with reference data"""
    print("\n" + "=" * 60)
    print("TEST 2: Nutrition Calculation WITH Reference Data")
    print("=" * 60)
    
    # New food items (some removed, some added)
    fooditems = [
        "raw salmon fillet",
        "chicken breast",
        "broccoli florets",
        "blueberries",
        "lentils"
    ]
    
    # Old food analysis as reference
    old_food_analysis = {
        "fooditems": [
            "raw salmon fillet",
            "chicken breast",
            "avocado cut in half"
        ],
        "nutrition": {
            "calories": 650,
            "protein": "55g",
            "carbohydrates": "15g",
            "fat": "40g",
            "fiber": "8g",
            "sugar": "5g"
        }
    }
    
    print(f"\nNew Food Items: {fooditems}")
    print(f"\nOld Food Analysis (Reference):")
    print(f"  Old Items: {old_food_analysis['fooditems']}")
    print(f"  Old Nutrition: {old_food_analysis['nutrition']}")
    print("\nCalling agent with reference...")
    
    response = await nutrition_calculator_agent(
        fooditems, 
        old_food_analysis=old_food_analysis
    )
    
    if response.success:
        print("\n✓ Agent call successful!")
        print(f"\nResponse Data:")
        print(f"  Food Items: {response.data.get('fooditems', [])}")
        print(f"  Nutrition: {response.data.get('nutrition', {})}")
        
        if hasattr(response, 'metadata'):
            print(f"\nMetadata:")
            print(f"  Model: {response.metadata.get('model_name', 'unknown')}")
            print(f"  Input Tokens: {response.metadata.get('input_tokens', 0)}")
            print(f"  Output Tokens: {response.metadata.get('output_tokens', 0)}")
    else:
        print(f"\n✗ Agent call failed: {response.error_message}")
    
    return response


async def test_consistency():
    """Test consistency between calculations"""
    print("\n" + "=" * 60)
    print("TEST 3: Consistency Check")
    print("=" * 60)
    
    # Same food items, calculated twice
    fooditems = ["1 grilled chicken breast", "1 cup cooked rice"]
    
    print(f"\nFood Items: {fooditems}")
    print("\nFirst calculation...")
    response1 = await nutrition_calculator_agent(fooditems)
    
    if not response1.success:
        print(f"✗ First calculation failed: {response1.error_message}")
        return
    
    nutrition1 = response1.data.get('nutrition', {})
    print(f"First Result: {nutrition1}")
    
    print("\nSecond calculation WITH first result as reference...")
    response2 = await nutrition_calculator_agent(
        fooditems,
        old_food_analysis={
            "fooditems": fooditems,
            "nutrition": nutrition1
        }
    )
    
    if not response2.success:
        print(f"✗ Second calculation failed: {response2.error_message}")
        return
    
    nutrition2 = response2.data.get('nutrition', {})
    print(f"Second Result: {nutrition2}")
    
    # Compare results
    print("\n" + "-" * 60)
    print("Consistency Analysis:")
    print("-" * 60)
    
    for key in nutrition1.keys():
        val1 = nutrition1.get(key)
        val2 = nutrition2.get(key)
        
        if val1 == val2:
            print(f"  ✓ {key}: {val1} == {val2}")
        else:
            print(f"  ⚠ {key}: {val1} != {val2} (variance detected)")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("NUTRITION CALCULATOR AGENT - REFERENCE DATA TESTS")
    print("=" * 60)
    
    try:
        # Test 1: Without reference
        await test_without_reference()
        
        # Test 2: With reference
        await test_with_reference()
        
        # Test 3: Consistency check
        await test_consistency()
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
