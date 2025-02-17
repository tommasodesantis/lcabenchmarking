from auth.credits import CreditsManager

def main():
    """Example script demonstrating how to manage user credits programmatically."""
    
    # Initialize the credits manager
    credits_manager = CreditsManager()
    
    # Example user email
    user_email = "user@example.com"
    
    # Get current credits
    current_credits = credits_manager.get_credits(user_email)
    print(f"Current credits for {user_email}: {current_credits}")
    
    # Add credits
    credits_to_add = 10
    credits_manager.add_credits(user_email, credits_to_add)
    print(f"Added {credits_to_add} credits")
    
    # Check updated credits
    updated_credits = credits_manager.get_credits(user_email)
    print(f"Updated credits: {updated_credits}")
    
    # Set credits to specific amount
    new_amount = 20
    credits_manager.set_credits(user_email, new_amount)
    print(f"Set credits to {new_amount}")
    
    # Verify final amount
    final_credits = credits_manager.get_credits(user_email)
    print(f"Final credits: {final_credits}")

if __name__ == "__main__":
    main()
