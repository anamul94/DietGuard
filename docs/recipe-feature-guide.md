# Recipe Suggestion Feature - Implementation Guide for Mobile Developers

This guide provides detailed instructions for mobile developers integrating the Recipe Suggestion feature into the DietGuard mobile application.

## Overview

The Recipe Suggestion feature allows users with doctor-prescribed diet restrictions to:
1. Upload diet charts for AI extraction
2. Review and confirm extracted restrictions
3. Generate personalized recipes
4. Create weekly meal schedules
5. Track recipes in the existing meal tracker

## User Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Home Screen]                                                      │
│       │                                                             │
│       ▼                                                             │
│  "Create Meal Plan from Doctor's Diet"                              │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────────────────────────────────┐                        │
│  │ Screen 1: Upload Options                │                        │
│  │  • Upload diet chart (image/PDF)        │                        │
│  │  • Enter restrictions manually          │                        │
│  └─────────────────┬───────────────────────┘                        │
│                    │                                                │
│       ┌────────────┴────────────┐                                   │
│       ▼                         ▼                                   │
│  ┌──────────────┐      ┌──────────────────┐                         │
│  │ Upload       │      │ Manual Entry     │                         │
│  │ Screen       │      │ Screen           │                         │
│  └──────┬───────┘      └────────┬─────────┘                         │
│         │                       │                                   │
│         ▼                       │                                   │
│  ┌─────────────────────────────┴─────────────────────┐              │
│  │ Screen 2: Review Extracted Restrictions           │              │
│  │  • Show extracted avoid/limit/allow lists         │              │
│  │  • Allow user to edit                             │              │
│  │  • [Confirm] button                               │              │
│  └─────────────────────┬─────────────────────────────┘              │
│                        │                                            │
│                        ▼                                            │
│  ┌─────────────────────────────────────────────────────┐            │
│  │ Screen 3: Preferences Setup                         │            │
│  │  • Cuisine selection (multi-select)                 │            │
│  │  • Diet type (veg/non-veg/vegan)                    │            │
│  │  • Allergies                                        │            │
│  │  • Disliked ingredients                             │            │
│  │  • Cooking time preference                          │            │
│  │  • [Save & Generate Plan]                           │            │
│  └─────────────────────┬───────────────────────────────┘            │
│                        │                                            │
│       ┌────────────────┴────────────────┐                           │
│       ▼                                 ▼                           │
│  ┌──────────────────┐        ┌──────────────────────┐               │
│  │ On-Demand        │        │ Weekly Schedule      │               │
│  │ Recipe Screen    │        │ Screen               │               │
│  │ (single recipe)  │        │ (7-day plan)         │               │
│  └────────┬─────────┘        └──────────┬───────────┘               │
│           │                             │                           │
│           └──────────────┬──────────────┘                           │
│                          ▼                                          │
│  ┌─────────────────────────────────────────────────────┐            │
│  │ Screen 4: Recipe Detail                             │            │
│  │  • Recipe name, description                         │            │
│  │  • Ingredients list                                 │            │
│  │  • Step-by-step instructions                        │            │
│  │  • Nutrition per serving                            │            │
│  │  • Diet match reasons                               │            │
│  │  • [Add to Tracker] [Favorite] buttons              │            │
│  └─────────────────────────────────────────────────────┘            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## API Integration

### 1. Upload Diet Chart

**Endpoint:** `POST /api/v1/health/recipes/diet-profiles/upload`

**Request:**
```swift
// Swift (iOS)
let url = URL(string: "\(baseURL)/api/v1/health/recipes/diet-profiles/upload")!
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

let boundary = UUID().uuidString
request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

var body = Data()
// Add file
body.append("--\(boundary)\r\n".data(using: .utf8)!)
body.append("Content-Disposition: form-data; name=\"file\"; filename=\"diet_chart.jpg\"\r\n".data(using: .utf8)!)
body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
body.append(imageData)
body.append("\r\n".data(using: .utf8)!)

// Add optional profile_name
body.append("--\(boundary)\r\n".data(using: .utf8)!)
body.append("Content-Disposition: form-data; name=\"profile_name\"\r\n\r\n".data(using: .utf8)!)
body.append("My Diet Plan".data(using: .utf8)!)
body.append("\r\n".data(using: .utf8)!)

body.append("--\(boundary)--\r\n".data(using: .utf8)!)
request.httpBody = body
```

```kotlin
// Kotlin (Android)
val url = "$baseUrl/api/v1/health/recipes/diet-profiles/upload"
val file = File(filePath)
val requestBody = MultipartBody.Builder()
    .setType(MultipartBody.FORM)
    .addFormDataPart("file", file.name, file.asRequestBody("image/jpeg".toMediaType()))
    .addFormDataPart("profile_name", "My Diet Plan")
    .build()

val request = Request.Builder()
    .url(url)
    .header("Authorization", "Bearer $accessToken")
    .post(requestBody)
    .build()
```

**Response Handling:**
```json
{
  "profile": {
    "id": "uuid",
    "extraction_status": "pending",
    "avoid_foods": ["sugar", "fried food"],
    "limit_foods": ["salt"],
    "allowed_foods": ["vegetables", "lean protein"]
  },
  "extraction_confidence": "high",
  "unreadable_sections": []
}
```

### 2. Review & Confirm Restrictions

**Screen: Restrictions Review**

Display extracted data and allow user to edit:

```swift
// iOS SwiftUI Example
struct RestrictionsReviewView: View {
    let profile: DietProfile
    @State private var avoidFoods: [String]
    @State private var limitFoods: [String]
    @State private var allowedFoods: [String]
    
    var body: some View {
        Form {
            Section("Foods to Avoid") {
                ForEach(avoidFoods, id: \.self) { food in
                    Text(food)
                }
                .onDelete { indexSet in
                    avoidFoods.remove(atOffsets: indexSet)
                }
                Button("+ Add") { /* add new */ }
            }
            
            Section("Foods to Limit") {
                ForEach(limitFoods, id: \.self) { food in
                    Text(food)
                }
            }
            
            Section("Allowed Foods") {
                ForEach(allowedFoods, id: \.self) { food in
                    Text(food)
                }
            }
        }
        .navigationTitle("Review Restrictions")
        .toolbar {
            Button("Confirm") {
                confirmRestrictions()
            }
        }
    }
    
    func confirmRestrictions() {
        // PATCH /api/v1/health/recipes/diet-profiles/{id}
        let payload: [String: Any] = [
            "extraction_status": "confirmed",
            "avoid_foods": avoidFoods,
            "limit_foods": limitFoods,
            "allowed_foods": allowedFoods
        ]
        // ... API call
    }
}
```

### 3. Set Preferences

**Endpoint:** `PATCH /api/v1/health/recipes/diet-profiles/{id}`

**Request Body:**
```json
{
  "cuisine": ["Indian", "Bengali"],
  "diet_type": "non_vegetarian",
  "allergies": ["nuts", "shellfish"],
  "disliked_ingredients": ["eggplant", "bitter_gourd"],
  "cooking_time_pref": "30_min",
  "budget_level": "medium"
}
```

**UI Components:**

| Field | UI Component | Options |
|-------|--------------|---------|
| `cuisine` | Multi-select chips | Indian, Italian, Chinese, Bengali, Thai, Mediterranean, Mughlai |
| `diet_type` | Single select | vegetarian, non_vegetarian, vegan |
| `allergies` | Multi-select chips | nuts, dairy, gluten, shellfish, egg, soy |
| `cooking_time_pref` | Single select | 15_min, 30_min, 60_min |
| `budget_level` | Single select | low, medium, premium |

### 4. Generate Single Recipe (On-Demand)

**Endpoint:** `POST /api/v1/health/recipes/suggest`

**Request:**
```json
{
  "diet_profile_id": "profile-uuid",
  "meal_type": "lunch",
  "cuisine_override": ["Italian"]
}
```

**Use Case:** User wants a specific meal suggestion right now.

### 5. Generate Weekly Schedule

**Endpoint:** `POST /api/v1/health/recipes/generate-schedule`

**Request:**
```json
{
  "diet_profile_id": "profile-uuid",
  "week_start_date": "2026-04-28",
  "cuisine_override": null
}
```

**Response:**
```json
{
  "id": "schedule-uuid",
  "week_start_date": "2026-04-28",
  "days": {
    "monday": {
      "breakfast": { "id": "recipe-uuid", "recipe_name": "...", ... },
      "lunch": { ... },
      "dinner": { ... },
      "snack": { ... }
    },
    "tuesday": { ... }
  }
}
```

### 6. Get Current Schedule

**Endpoint:** `GET /api/v1/health/recipes/schedules/current`

Call this when user opens the weekly schedule screen.

### 7. Recipe Detail Screen

Display full recipe information:

```swift
struct RecipeDetailView: View {
    let recipe: Recipe
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Header
                Text(recipe.recipeName)
                    .font(.title)
                    .bold()
                
                Text(recipe.cuisine)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                // Nutrition Card
                HStack {
                    NutritionBadge(value: recipe.nutrition.calories, unit: "kcal", label: "Calories")
                    NutritionBadge(value: recipe.nutrition.proteinG, unit: "g", label: "Protein")
                    NutritionBadge(value: recipe.nutrition.carbsG, unit: "g", label: "Carbs")
                    NutritionBadge(value: recipe.nutrition.fatG, unit: "g", label: "Fat")
                }
                
                // Diet Match Reasons
                if !recipe.dietMatchReasons.isEmpty {
                    Section("Why This Fits Your Diet") {
                        ForEach(recipe.dietMatchReasons, id: \.self) { reason in
                            Label(reason, systemImage: "checkmark.circle.fill")
                                .foregroundColor(.green)
                        }
                    }
                }
                
                // Warnings
                if !recipe.warnings.isEmpty {
                    Section("⚠️ Warnings") {
                        ForEach(recipe.warnings, id: \.self) { warning in
                            Text(warning)
                                .foregroundColor(.orange)
                        }
                    }
                }
                
                // Ingredients
                Section("Ingredients") {
                    ForEach(recipe.ingredients, id: \.name) { ingredient in
                        HStack {
                            Text(ingredient.name)
                            Spacer()
                            Text(ingredient.quantity)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                // Instructions
                Section("Instructions") {
                    ForEach(recipe.instructions, id: \.stepNumber) { step in
                        HStack(alignment: .top) {
                            Text("\(step.stepNumber).")
                                .bold()
                            Text(step.instruction)
                        }
                    }
                }
            }
            .padding()
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    // PATCH /api/v1/health/recipes/{id}/favorite
                } label: {
                    Image(systemName: recipe.isFavorite ? "heart.fill" : "heart")
                }
            }
            ToolbarItem(placement: .secondaryAction) {
                Button("Add to Tracker") {
                    // POST /api/v1/health/recipes/{id}/track
                }
            }
        }
    }
}
```

### 8. Track Recipe

**Endpoint:** `POST /api/v1/health/recipes/{id}/track`

```json
{
  "recipe_id": "recipe-uuid",
  "scheduled_date": "2026-04-28",
  "status": "ate"
}
```

**Status Options:**
- `cooked` - User prepared the recipe
- `ate` - User ate the meal
- `skipped` - User skipped this meal
- `replaced` - User ate something else

When status is `cooked` or `ate`, the recipe's nutrition is automatically added to the meal tracker.

## Data Models

### DietProfile
```swift
struct DietProfile: Codable {
    let id: String
    let userId: String
    let profileName: String?
    let medicalCondition: String?
    let avoidFoods: [String]
    let limitFoods: [String]
    let allowedFoods: [String]
    let mealFrequency: Int?
    let calorieLimit: Int?
    let saltLimit: String?
    let doctorNotes: String?
    let extractionStatus: String  // "pending", "confirmed", "edited"
    let cuisine: [String]
    let dietType: String?
    let allergies: [String]
    let dislikedIngredients: [String]
    let cookingTimePref: String?
    let budgetLevel: String?
    let isActive: Bool
    let createdAt: String
    let updatedAt: String
}
```

### Recipe
```swift
struct Recipe: Codable {
    let id: String
    let userId: String
    let dietProfileId: String?
    let recipeName: String
    let cuisine: String?
    let mealType: String
    let description: String?
    let ingredients: [Ingredient]
    let instructions: [Instruction]
    let prepTimeMinutes: Int?
    let cookTimeMinutes: Int?
    let servings: Int
    let nutrition: Nutrition
    let dietMatchReasons: [String]
    let warnings: [String]
    let isFavorite: Bool
    let sourceType: String  // "on_demand" or "weekly_schedule"
    let createdAt: String
}

struct Ingredient: Codable {
    let name: String
    let quantity: String
    let notes: String?
}

struct Instruction: Codable {
    let stepNumber: Int
    let instruction: String
}

struct Nutrition: Codable {
    let calories: Int
    let proteinG: Float
    let carbsG: Float
    let fatG: Float
    let fiberG: Float?
    let sodiumMg: Float?
    let sugarG: Float?
}
```

### WeeklySchedule
```swift
struct WeeklySchedule: Codable {
    let id: String
    let userId: String
    let dietProfileId: String?
    let weekStartDate: String
    let complianceScore: Int
    let isActive: Bool
    let createdAt: String
    let days: [String: [String: Recipe]]  // day -> mealType -> Recipe
}
```

## Error Handling

### Common Error Responses

```json
{
  "detail": "Diet profile not found"
}
```

```json
{
  "detail": "This does not appear to be a diet chart. Please upload a medical document."
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 401 | Unauthorized - Invalid or expired token |
| 403 | Forbidden - Subscription limit reached |
| 404 | Not found - Profile/recipe doesn't exist |
| 413 | File too large |
| 422 | Validation error - Invalid file format or request body |
| 500 | Server error - Try again later |

## UI/UX Recommendations

### Loading States
- Recipe generation may take 5-15 seconds
- Show a loading indicator with progress text
- Consider skeleton screens for recipe lists

### Empty States
- No diet profiles: "Create your first diet plan from your doctor's recommendations"
- No recipes: "Generate your first recipe suggestion"
- No schedule: "Create a weekly meal plan"

### Safety Disclaimer
Always display on recipe screens:
> "These meal suggestions are based on your uploaded diet instructions. Please consult your doctor or dietitian before making major diet changes."

### Offline Support
- Cache the current weekly schedule locally
- Cache favorite recipes
- Show cached content when offline

## Testing Checklist

- [ ] Upload diet chart (image)
- [ ] Upload diet chart (PDF)
- [ ] Manual diet profile creation
- [ ] Edit extracted restrictions
- [ ] Set cuisine preferences
- [ ] Set allergies
- [ ] Generate single recipe (breakfast, lunch, dinner, snack)
- [ ] Generate weekly schedule
- [ ] View recipe details
- [ ] Add recipe to favorites
- [ ] Remove from favorites
- [ ] Track recipe (ate, skipped, replaced)
- [ ] Verify nutrition is added to daily tracker
- [ ] Error handling for invalid file types
- [ ] Error handling for subscription limits

## Support

For API questions, contact: support@dietguard.com

For bug reports, open an issue on GitHub.
